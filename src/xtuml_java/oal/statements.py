"""Penerjemah statement OAL -> blok statement Java."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from ..ir.model import (
    VOID,
    Model,
    TypeRef,
    XtClass,
    safe_ident,
    setter_name,
)
from .expressions import OalContext, _split_args, translate_expr


def _parse_chain(chain_str: str, ctx: OalContext) -> Tuple[str, TypeRef, List[Tuple[str, XtClass, Optional[str]]]]:
    """Mem-parse rantai navigasi seperti 'veh->R4[ParkingSession]' atau 'self->R1[contains]->R2[operated by]'."""
    parts = [p.strip() for p in chain_str.split("->")]
    if len(parts) < 2:
        raise ValueError(f"Rantai relasi tidak valid: {chain_str}")

    root_expr, root_type = translate_expr(parts[0], ctx)
    cur_type = root_type
    hops: List[Tuple[str, XtClass, Optional[str]]] = []

    for seg in parts[1:]:
        # Format: R4[ParkingSession] atau R1[contains] atau R1
        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[([^\]]+)\])?", seg)
        if not m:
            raise ValueError(f"Segmen relasi tidak valid: {seg}")
        rel_id, qualifier = m.groups()
        rel = ctx.model.get_relationship(rel_id)
        if rel is None:
            raise ValueError(f"Relasi '{rel_id}' tidak ditemukan.")

        cur_cls = ctx.model.class_of_ref(cur_type)
        phrase: Optional[str] = None
        target_cls: Optional[XtClass] = None

        if rel.kind == "generalization":
            if qualifier:
                target_cls = ctx.model.resolve_class(qualifier.strip())
            if target_cls is None:
                raise ValueError(f"Generalisasi '{rel_id}' memerlukan nama kelas target di dalam [...].")
        else:
            # Cek apakah qualifier adalah nama kelas (mis. ParkingSession) atau phrase (mis. 'contains')
            if qualifier:
                q = qualifier.strip().strip("'\"")
                by_cls = ctx.model.resolve_class(q)
                if by_cls is not None and by_cls.name in ctx.model.relationship_classes(rel):
                    target_cls = by_cls
                else:
                    phrase = q

            # Tentukan target_cls jika belum dikunci oleh qualifier
            if target_cls is None:
                if cur_cls and rel.assoc_class == cur_cls.name:
                    # Navigasi dari association class ke salah satu ujung
                    for end in rel.ends:
                        if phrase is None or end.phrase == phrase:
                            target_cls = ctx.model.get_class(end.class_name)
                            break
                elif cur_cls:
                    for idx, end in enumerate(rel.ends):
                        end_cls = ctx.model.get_class(end.class_name)
                        if end_cls and (end_cls.name == cur_cls.name or ctx.model.is_subtype_of(cur_cls, end_cls)):
                            if phrase is None or end.phrase == phrase:
                                other_end = rel.ends[1 - idx]
                                target_cls = ctx.model.get_class(other_end.class_name)
                                break
            if target_cls is None:
                raise ValueError(f"Tidak dapat menentukan kelas target pada navigasi '{seg}'.")

        hops.append((rel_id, target_cls, phrase))
        cur_type = TypeRef("inst_ref", target_cls.name)

    return root_expr, root_type, hops


def _emit_navigation(
    cardinality: str,
    var_name: str,
    chain_str: str,
    where_raw: Optional[str],
    ctx: OalContext,
) -> str:
    root_expr, root_type, hops = _parse_chain(chain_str, ctx)
    is_many = cardinality == "many"
    is_collection = root_type.kind == "inst_ref_set"

    cur_expr = root_expr
    final_cls = hops[-1][1]

    for idx, (rel_id, target_cls, phrase) in enumerate(hops):
        is_last = idx == len(hops) - 1
        phrase_lit = f'"{phrase}"' if phrase else "null"
        if not is_collection and is_last and not is_many and not where_raw:
            cur_expr = f'Relationships.navigateOne({cur_expr}, "{rel_id}", {target_cls.name}.class, {phrase_lit})'
        elif is_collection:
            cur_expr = f'Relationships.navigateAll({cur_expr}, "{rel_id}", {target_cls.name}.class, {phrase_lit})'
            is_collection = True
        else:
            cur_expr = f'Relationships.navigate({cur_expr}, "{rel_id}", {target_cls.name}.class, {phrase_lit})'
            is_collection = True

    if where_raw:
        sub_ctx = ctx.copy()
        sub_ctx.selected_type = TypeRef("inst_ref", final_cls.name)
        cond_j, _ = translate_expr(where_raw, sub_ctx)
        stream_op = "collect(java.util.stream.Collectors.toList())" if is_many else "findFirst().orElse(null)"
        cur_expr = f"{cur_expr}.stream().filter(selected -> {cond_j}).{stream_op}"
    elif not is_many and is_collection:
        cur_expr = f"Ops.first({cur_expr})"

    jvar = safe_ident(var_name)
    res_type = TypeRef("inst_ref_set" if is_many else "inst_ref", final_cls.name)

    if var_name in ctx.vars:
        return f"{jvar} = {cur_expr};"
    ctx.vars[var_name] = res_type
    jtype = ctx.model.java_type(res_type)
    return f"{jtype} {jvar} = {cur_expr};"


def translate_single_statement(stmt: str, ctx: OalContext) -> str:
    """Menerjemahkan satu statement OAL (tanpa blok if/for) ke satu baris statement Java."""
    s = stmt.strip()
    if s.endswith(";"):
        s = s[:-1].strip()

    # 1. create object instance <var> of <KEY_LETTERS_OR_CLASS>
    m_create = re.fullmatch(r"create\s+object\s+instance\s+([A-Za-z_][A-Za-z0-9_]*)\s+of\s+([A-Za-z_][A-Za-z0-9_]*)", s)
    if m_create:
        vname, cls_ref = m_create.groups()
        target_cls = ctx.model.resolve_class(cls_ref)
        if target_cls is None:
            raise ValueError(f"Kelas '{cls_ref}' tidak ditemukan.")
        if target_cls.is_abstract:
            raise ValueError(f"Tidak dapat membuat instance dari kelas abstrak '{target_cls.name}'.")
        jvar = safe_ident(vname)
        tref = TypeRef("inst_ref", target_cls.name)
        if vname in ctx.vars:
            return f"{jvar} = new {target_cls.name}();"
        ctx.vars[vname] = tref
        return f"{target_cls.name} {jvar} = new {target_cls.name}();"

    # 2. delete object instance <var>
    m_del = re.fullmatch(r"delete\s+object\s+instance\s+([A-Za-z_][A-Za-z0-9_]*)", s)
    if m_del:
        vname = m_del.group(1)
        vj, _ = translate_expr(vname, ctx)
        return f"Store.delete({vj});"

    # 3. relate <x> to <y> across <R#> [using <assoc>]
    m_rel = re.fullmatch(
        r"relate\s+([A-Za-z_][A-Za-z0-9_]*)\s+to\s+([A-Za-z_][A-Za-z0-9_]*)\s+across\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+using\s+([A-Za-z_][A-Za-z0-9_]*))?",
        s,
    )
    if m_rel:
        x_var, y_var, rel_id, assoc_var = m_rel.groups()
        if ctx.model.get_relationship(rel_id) is None:
            raise ValueError(f"Relasi '{rel_id}' tidak ditemukan.")
        xj, _ = translate_expr(x_var, ctx)
        yj, _ = translate_expr(y_var, ctx)
        if assoc_var:
            aj, _ = translate_expr(assoc_var, ctx)
            return f'Relationships.relate("{rel_id}", {xj}, {yj}, {aj});'
        return f'Relationships.relate("{rel_id}", {xj}, {yj});'

    # 4. unrelate <x> from <y> across <R#> [using <assoc>]
    m_unrel = re.fullmatch(
        r"unrelate\s+([A-Za-z_][A-Za-z0-9_]*)\s+from\s+([A-Za-z_][A-Za-z0-9_]*)\s+across\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+using\s+([A-Za-z_][A-Za-z0-9_]*))?",
        s,
    )
    if m_unrel:
        x_var, y_var, rel_id, assoc_var = m_unrel.groups()
        if ctx.model.get_relationship(rel_id) is None:
            raise ValueError(f"Relasi '{rel_id}' tidak ditemukan.")
        xj, _ = translate_expr(x_var, ctx)
        yj, _ = translate_expr(y_var, ctx)
        if assoc_var:
            aj, _ = translate_expr(assoc_var, ctx)
            return f'Relationships.unrelate("{rel_id}", {xj}, {yj}, {aj});'
        return f'Relationships.unrelate("{rel_id}", {xj}, {yj});'

    # 5. select any|many <var> from instances of <CLS> [where (<cond>)]
    m_sel_inst = re.fullmatch(
        r"select\s+(any|many)\s+([A-Za-z_][A-Za-z0-9_]*)\s+from\s+instances\s+of\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+where\s+(.+))?",
        s,
    )
    if m_sel_inst:
        card, vname, cls_ref, where_raw = m_sel_inst.groups()
        target_cls = ctx.model.resolve_class(cls_ref)
        if target_cls is None:
            raise ValueError(f"Kelas '{cls_ref}' tidak ditemukan.")
        if where_raw:
            sub_ctx = ctx.copy()
            sub_ctx.selected_type = TypeRef("inst_ref", target_cls.name)
            cond_j, _ = translate_expr(where_raw, sub_ctx)
            pred = f"selected -> {cond_j}"
        else:
            pred = "null"
        fn = "Store.selectMany" if card == "many" else "Store.selectAny"
        res_type = TypeRef("inst_ref_set" if card == "many" else "inst_ref", target_cls.name)
        jvar = safe_ident(vname)
        call = f"{fn}({target_cls.name}.class, {pred})"
        if vname in ctx.vars:
            return f"{jvar} = {call};"
        ctx.vars[vname] = res_type
        return f"{ctx.model.java_type(res_type)} {jvar} = {call};"

    # 6. select one|any|many <var> related by <chain> [where (<cond>)]
    m_sel_rel = re.fullmatch(
        r"select\s+(one|any|many)\s+([A-Za-z_][A-Za-z0-9_]*)\s+related\s+by\s+(.+?)(?:\s+where\s+(.+))?",
        s,
    )
    if m_sel_rel:
        card, vname, chain_str, where_raw = m_sel_rel.groups()
        return _emit_navigation(card, vname, chain_str.strip(), where_raw, ctx)

    # 7. generate <ClassOrKey>:<Event>(p1: v1, ...) to <target>
    m_gen = re.fullmatch(
        r"generate\s+([A-Za-z_][A-Za-z0-9_]*):([A-Za-z_][A-Za-z0-9_]*)\((.*)\)\s+to\s+([A-Za-z_][A-Za-z0-9_]*)",
        s,
    )
    if m_gen:
        cls_ref, ev_name, args_raw, target_var = m_gen.groups()
        ev_owner = ctx.model.resolve_class(cls_ref)
        if ev_owner is None or ev_owner.state_machine is None or ev_owner.state_machine.event(ev_name) is None:
            raise ValueError(f"Event '{cls_ref}:{ev_name}' tidak ditemukan pada state machine.")
        target_j, _ = translate_expr(target_var, ctx)
        raw_parts = _split_args(args_raw)
        if not raw_parts:
            return f'Runtime.generate({target_j}, new Event("{ev_name}"));'
        kv_items: List[str] = []
        for idx, p in enumerate(raw_parts):
            if ":" in p and not p.lstrip().startswith('"'):
                k, v = p.split(":", 1)
                vj, _ = translate_expr(v.strip(), ctx)
                kv_items.append(f'"{k.strip()}", {vj}')
            else:
                ev_def = ev_owner.state_machine.event(ev_name)
                pname = ev_def.params[idx].name if (ev_def and idx < len(ev_def.params)) else f"arg{idx}"
                vj, _ = translate_expr(p, ctx)
                kv_items.append(f'"{pname}", {vj}')
        return f'Runtime.generate({target_j}, Event.of("{ev_name}", {", ".join(kv_items)}));'

    # 8. return [<expr>]
    if s == "return":
        return "return;"
    m_ret = re.fullmatch(r"return\s+(.+)", s)
    if m_ret:
        rj, _ = translate_expr(m_ret.group(1), ctx)
        return f"return {rj};"

    # 9. Attribute assignment: <obj>.<attr> = <expr>
    m_attr_assign = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", s)
    if m_attr_assign:
        obj_name, attr_name, rhs = m_attr_assign.groups()
        target_j, target_type = translate_expr(obj_name, ctx)
        target_cls = ctx.model.class_of_ref(target_type)
        if target_cls is None:
            raise ValueError(f"Target '{obj_name}' bukan instance class.")
        attr = ctx.model.find_attribute(target_cls, attr_name)
        if attr is None:
            raise ValueError(f"Atribut '{attr_name}' tidak ditemukan di '{target_cls.name}'.")
        rhs_j, _ = translate_expr(rhs, ctx)
        return f"{target_j}.{setter_name(attr_name)}({rhs_j});"

    # 10. Local variable assignment: [assign] <var> = <expr>
    m_var_assign = re.fullmatch(r"(?:assign\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", s)
    if m_var_assign:
        vname, rhs = m_var_assign.groups()
        rhs_j, rhs_t = translate_expr(rhs, ctx)
        jvar = safe_ident(vname)
        if vname in ctx.vars:
            return f"{jvar} = {rhs_j};"
        if rhs_t == VOID:
            raise ValueError(f"Tidak dapat menginferensi tipe variabel '{vname}'.")
        ctx.vars[vname] = rhs_t
        return f"{ctx.model.java_type(rhs_t)} {jvar} = {rhs_j};"

    # 11. Operation invocation statement: <obj>.<op>(...)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\(.*\)", s):
        call_j, _ = translate_expr(s, ctx)
        return f"{call_j};"

    raise ValueError(f"Statement OAL tidak dikenali: {stmt}")