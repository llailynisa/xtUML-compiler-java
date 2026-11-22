"""Entry point penerjemah blok OAL menjadi baris-baris kode Java yang aman dikompilasi javac."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..ir.model import VOID, Model, TypeRef, XtClass, safe_ident
from .expressions import OalContext, translate_expr
from .statements import translate_single_statement


@dataclass
class ActionResult:
    lines: List[str] = field(default_factory=list)
    todos: List[str] = field(default_factory=list)


def translate_action(
    model: Model,
    oal_lines: List[str],
    cls: Optional[XtClass] = None,
    params: Optional[Dict[str, TypeRef]] = None,
    return_type: TypeRef = VOID,
    kind: str = "operation",
    indent: int = 2,
) -> ActionResult:
    """Menerjemahkan daftar baris OAL menjadi ActionResult(lines, todos)."""
    ctx = OalContext(
        model=model,
        cls=cls,
        vars=dict(params) if params else {},
        has_rcvd_evt=(kind == "state"),
        event_params=dict(params) if (kind == "state" and params) else {},
    )

    out_lines: List[str] = []
    todos: List[str] = []
    cur_indent = indent
    block_stack: List[str] = []  # "if" | "for"

    def emit(line: str, level: Optional[int] = None) -> None:
        lvl = cur_indent if level is None else level
        out_lines.append(("    " * lvl) + line)

    for raw_line in oal_lines:
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("//"):
            emit(stripped)
            continue

        clean = stripped[:-1].strip() if stripped.endswith(";") else stripped

        # --- Kontrol alur: IF ---
        m_if = re.fullmatch(r"if\s*(.+)", clean)
        if m_if and not clean.startswith("if_"):
            try:
                cond_j, _ = translate_expr(m_if.group(1), ctx)
                emit(f"if ({cond_j}) {{")
                block_stack.append("if")
                cur_indent += 1
            except Exception as ex:
                todos.append(f"{stripped} ({ex})")
                emit(f"// TODO: {stripped}")
                emit("if (Ops.bool(false)) {")
                block_stack.append("if")
                cur_indent += 1
            continue

        # --- Kontrol alur: ELIF ---
        m_elif = re.fullmatch(r"elif\s*(.+)", clean)
        if m_elif:
            if block_stack and block_stack[-1] == "if":
                cur_indent -= 1
                try:
                    cond_j, _ = translate_expr(m_elif.group(1), ctx)
                    emit(f"}} else if ({cond_j}) {{")
                except Exception as ex:
                    todos.append(f"{stripped} ({ex})")
                    emit(f"}} else if (Ops.bool(false)) {{ // TODO: {stripped}")
                cur_indent += 1
            else:
                todos.append(stripped)
                emit(f"// TODO: {stripped}")
            continue

        # --- Kontrol alur: ELSE ---
        if clean == "else":
            if block_stack and block_stack[-1] == "if":
                cur_indent -= 1
                emit("} else {")
                cur_indent += 1
            else:
                todos.append(stripped)
                emit(f"// TODO: {stripped}")
            continue

        # --- Kontrol alur: END IF ---
        if clean == "end if":
            if block_stack and block_stack[-1] == "if":
                block_stack.pop()
                cur_indent -= 1
                emit("}")
            else:
                todos.append(stripped)
                emit(f"// TODO: {stripped}")
            continue

        # --- Kontrol alur: FOR EACH <item> IN <collection> ---
        m_for = re.fullmatch(r"for\s+each\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([A-Za-z_][A-Za-z0-9_]*)", clean)
        if m_for:
            item_var, col_var = m_for.groups()
            try:
                col_j, col_t = translate_expr(col_var, ctx)
                if col_t.kind != "inst_ref_set" or not col_t.target:
                    raise ValueError(f"'{col_var}' bukan inst_ref_set.")
                item_cls = model.resolve_class(col_t.target)
                if item_cls is None:
                    raise ValueError(f"Kelas '{col_t.target}' tidak ditemukan.")
                ctx.vars[item_var] = TypeRef("inst_ref", item_cls.name)
                emit(f"for ({item_cls.name} {safe_ident(item_var)} : {col_j}) {{")
                block_stack.append("for")
                cur_indent += 1
            except Exception as ex:
                todos.append(f"{stripped} ({ex})")
                emit(f"// TODO: {stripped}")
                emit("if (Ops.bool(false)) {")
                block_stack.append("for")
                cur_indent += 1
            continue

        # --- Kontrol alur: END FOR ---
        if clean == "end for":
            if block_stack and block_stack[-1] == "for":
                block_stack.pop()
                cur_indent -= 1
                emit("}")
            else:
                todos.append(stripped)
                emit(f"// TODO: {stripped}")
            continue

        # --- Statement tunggal ---
        try:
            java_stmt = translate_single_statement(stripped, ctx)
            emit(java_stmt)
        except Exception as ex:
            todos.append(f"{stripped} ({ex})")
            emit(f"// TODO: {stripped}")

    # Tutup blok yang lupa diakhiri 'end if' / 'end for' agar file tetap valid di javac
    while block_stack:
        block_stack.pop()
        cur_indent -= 1
        emit("} // TODO: auto-closed block")

    return ActionResult(lines=out_lines, todos=todos)