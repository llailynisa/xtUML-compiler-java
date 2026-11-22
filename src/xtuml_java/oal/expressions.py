"""Penerjemah ekspresi OAL -> ekspresi Java."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..ir.model import (
    BOOLEAN,
    INTEGER,
    REAL,
    STRING,
    VOID,
    Model,
    TypeRef,
    XtClass,
    getter_name,
    safe_ident,
)


@dataclass
class OalContext:
    model: Model
    cls: Optional[XtClass] = None
    vars: Dict[str, TypeRef] = field(default_factory=dict)
    selected_type: Optional[TypeRef] = None
    has_rcvd_evt: bool = False
    event_params: Dict[str, TypeRef] = field(default_factory=dict)

    def copy(self) -> "OalContext":
        return OalContext(
            model=self.model,
            cls=self.cls,
            vars=dict(self.vars),
            selected_type=self.selected_type,
            has_rcvd_evt=self.has_rcvd_evt,
            event_params=dict(self.event_params),
        )


def _split_top_level(expr: str, operators: Tuple[str, ...]) -> Optional[Tuple[str, str, str]]:
    """Memecah ekspresi pada operator di level kurung 0 (dari kanan ke kiri untuk asosiatif kiri)."""
    depth = 0
    in_str = False
    escape = False
    i = len(expr) - 1
    while i >= 0:
        ch = expr[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            i -= 1
            continue
        if ch == '"':
            in_str = True
            i -= 1
            continue
        if ch == ")":
            depth += 1
            i -= 1
            continue
        if ch == "(":
            depth -= 1
            i -= 1
            continue
        if depth == 0:
            for op in operators:
                plen = len(op)
                start = i - plen + 1
                if start >= 0 and expr[start : i + 1] == op:
                    # Pastikan operator kata (and/or) memiliki batas kata
                    if op.isalpha():
                        before_ok = start == 0 or not (expr[start - 1].isalnum() or expr[start - 1] == "_")
                        after_ok = (i + 1 == len(expr)) or not (expr[i + 1].isalnum() or expr[i + 1] == "_")
                        if not (before_ok and after_ok):
                            continue
                    # Hindari memecah == atau != saat mencari =
                    if op in ("<", ">") and i + 1 < len(expr) and expr[i + 1] == "=":
                        continue
                    left = expr[:start].strip()
                    right = expr[i + 1 :].strip()
                    if left and right:
                        return left, op, right
        i -= 1
    return None


def _strip_outer_parens(expr: str) -> str:
    expr = expr.strip()
    while expr.startswith("(") and expr.endswith(")"):
        depth = 0
        in_str = False
        escape = False
        balanced = True
        for idx, ch in enumerate(expr):
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and idx != len(expr) - 1:
                    balanced = False
                    break
        if balanced and depth == 0:
            expr = expr[1:-1].strip()
        else:
            break
    return expr


def _split_args(arg_str: str) -> List[str]:
    if not arg_str.strip():
        return []
    parts: List[str] = []
    depth = 0
    in_str = False
    escape = False
    start = 0
    for i, ch in enumerate(arg_str):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(arg_str[start:i].strip())
            start = i + 1
    parts.append(arg_str[start:].strip())
    return parts


def translate_expr(expr: str, ctx: OalContext) -> Tuple[str, TypeRef]:
    """Menerjemahkan ekspresi OAL menjadi (kode_java, inferensi_TypeRef)."""
    e = _strip_outer_parens(expr)
    if not e:
        return "", VOID

    # 1. Logical OR
    split = _split_top_level(e, ("or", "||"))
    if split:
        l_code, _, r_code = split
        lj, _ = translate_expr(l_code, ctx)
        rj, _ = translate_expr(r_code, ctx)
        return f"({lj} || {rj})", BOOLEAN

    # 2. Logical AND
    split = _split_top_level(e, ("and", "&&"))
    if split:
        l_code, _, r_code = split
        lj, _ = translate_expr(l_code, ctx)
        rj, _ = translate_expr(r_code, ctx)
        return f"({lj} && {rj})", BOOLEAN

    # 3. Unary NOT
    m_not = re.fullmatch(r"(?:not\s+|!\s*)(.+)", e)
    if m_not:
        inner_j, _ = translate_expr(m_not.group(1), ctx)
        return f"(!{inner_j})", BOOLEAN

    # 4. Equality (==, !=)
    split = _split_top_level(e, ("==", "!="))
    if split:
        l_code, op, r_code = split
        lj, lt = translate_expr(l_code, ctx)
        rj, rt = translate_expr(r_code, ctx)
        if lt.kind == "string" or rt.kind == "string":
            eq_call = f"Ops.eq({lj}, {rj})"
            return (eq_call if op == "==" else f"!{eq_call}"), BOOLEAN
        return f"({lj} {op} {rj})", BOOLEAN

    # 5. Relational (<, >, <=, >=)
    split = _split_top_level(e, ("<=", ">=", "<", ">"))
    if split:
        l_code, op, r_code = split
        lj, _ = translate_expr(l_code, ctx)
        rj, _ = translate_expr(r_code, ctx)
        return f"({lj} {op} {rj})", BOOLEAN

    # 6. Additive (+, -)
    split = _split_top_level(e, ("+", "-"))
    if split:
        l_code, op, r_code = split
        lj, lt = translate_expr(l_code, ctx)
        rj, rt = translate_expr(r_code, ctx)
        if op == "+" and (lt.kind == "string" or rt.kind == "string"):
            return f"({lj} + {rj})", STRING
        res_t = REAL if (lt.kind == "real" or rt.kind == "real") else INTEGER
        return f"({lj} {op} {rj})", res_t

    # 7. Multiplicative (*, /, %)
    split = _split_top_level(e, ("*", "/", "%"))
    if split:
        l_code, op, r_code = split
        lj, lt = translate_expr(l_code, ctx)
        rj, rt = translate_expr(r_code, ctx)
        res_t = REAL if (lt.kind == "real" or rt.kind == "real") else INTEGER
        return f"({lj} {op} {rj})", res_t

    # 8. Built-in unary OAL functions: empty, not_empty, cardinality
    m_builtin = re.fullmatch(r"(empty|not_empty|cardinality)\s*(?:\((.+)\)|\s+([A-Za-z_][A-Za-z0-9_.]*))", e)
    if m_builtin:
        fn, arg_paren, arg_space = m_builtin.groups()
        raw_arg = arg_paren if arg_paren is not None else arg_space
        aj, _ = translate_expr(raw_arg, ctx)
        java_fn = {"empty": "Ops.empty", "not_empty": "Ops.notEmpty", "cardinality": "Ops.cardinality"}[fn]
        ret_t = INTEGER if fn == "cardinality" else BOOLEAN
        return f"{java_fn}({aj})", ret_t

    # 9. Enum literal: EnumName::VALUE -> EnumName.VALUE
    m_enum = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)::([A-Za-z_][A-Za-z0-9_]*)", e)
    if m_enum:
        ename, val = m_enum.groups()
        if ctx.model.get_enum(ename):
            return f"{ename}.{val}", TypeRef("enum", ename)
        raise ValueError(f"Enum '{ename}' tidak ditemukan.")

    # 10. String literal
    if len(e) >= 2 and e.startswith('"') and e.endswith('"'):
        return e, STRING

    # 11. Boolean / null / numeric literals
    if e in ("true", "false"):
        return f"Ops.bool({e})", BOOLEAN
    if e == "null":
        return "null", VOID
    if re.fullmatch(r"-?\d+", e):
        return e, INTEGER
    if re.fullmatch(r"-?\d+\.\d+", e):
        return e, REAL

    # 12. Method call pada objek: target.op(p1: val1, ...) atau target.op(val1)
    m_call = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\((.*)\)", e)
    if m_call:
        target_name, op_name, args_raw = m_call.groups()
        target_java, target_type = _resolve_target(target_name, ctx)
        target_cls = ctx.model.class_of_ref(target_type)
        op_def = ctx.model.find_operation(target_cls, op_name) if target_cls else None

        raw_parts = _split_args(args_raw)
        if op_def and op_def.params:
            # Dukung argumen bernama (veh: car) maupun posisional (car)
            named_map: Dict[str, str] = {}
            pos_list: List[str] = []
            for p in raw_parts:
                if ":" in p and not p.lstrip().startswith('"'):
                    k, v = p.split(":", 1)
                    vj, _ = translate_expr(v.strip(), ctx)
                    named_map[k.strip()] = vj
                else:
                    vj, _ = translate_expr(p, ctx)
                    pos_list.append(vj)
            ordered_args: List[str] = []
            for idx, param in enumerate(op_def.params):
                if param.name in named_map:
                    ordered_args.append(named_map[param.name])
                elif idx < len(pos_list):
                    ordered_args.append(pos_list[idx])
            ret_t = op_def.return_type
            return f"{target_java}.{op_name}({', '.join(ordered_args)})", ret_t
        else:
            args_j = []
            for p in raw_parts:
                val_part = p.split(":", 1)[1].strip() if (":" in p and not p.lstrip().startswith('"')) else p
                vj, _ = translate_expr(val_part, ctx)
                args_j.append(vj)
            ret_t = op_def.return_type if op_def else VOID
            return f"{target_java}.{op_name}({', '.join(args_j)})", ret_t

    # 13. Member access: self.attr, selected.attr, rcvd_evt.param, var.attr
    m_member = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)", e)
    if m_member:
        obj_name, member = m_member.groups()
        if obj_name == "rcvd_evt":
            if not ctx.has_rcvd_evt:
                raise ValueError("rcvd_evt hanya tersedia di dalam state action.")
            ptype = ctx.event_params.get(member, VOID)
            jtype = ctx.model.java_type(ptype, boxed=True) if ptype != VOID else "Object"
            return f"(({jtype}) rcvd_evt.get(\"{member}\"))", ptype

        target_java, target_type = _resolve_target(obj_name, ctx)
        target_cls = ctx.model.class_of_ref(target_type)
        if target_cls is None:
            raise ValueError(f"Tidak dapat mengakses atribut '{member}' pada '{obj_name}'.")
        attr = ctx.model.find_attribute(target_cls, member)
        if attr is None:
            raise ValueError(f"Atribut '{member}' tidak ditemukan pada kelas '{target_cls.name}'.")
        return f"{target_java}.{getter_name(member)}()", attr.type

    # 14. Simple identifier: self, selected, atau variabel lokal/parameter
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", e):
        return _resolve_target(e, ctx)

    raise ValueError(f"Ekspresi OAL tidak dikenali: {expr}")


def _resolve_target(name: str, ctx: OalContext) -> Tuple[str, TypeRef]:
    if name == "self":
        if ctx.cls is None:
            raise ValueError("'self' tidak tersedia di konteks ini.")
        return "this", TypeRef("inst_ref", ctx.cls.name)
    if name == "selected":
        if ctx.selected_type is None:
            raise ValueError("'selected' hanya tersedia di dalam klausa where.")
        return "selected", ctx.selected_type
    if name in ctx.vars:
        return safe_ident(name), ctx.vars[name]
    raise ValueError(f"Variabel '{name}' belum dideklarasikan.")