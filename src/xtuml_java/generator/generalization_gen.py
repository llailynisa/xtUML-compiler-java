"""Generalisasi/spesialisasi: supertype -> abstract class, subtype -> extends."""
from __future__ import annotations

from typing import List

from ..ir.model import Model, XtClass


def superclass_name(model: Model, cls: XtClass) -> str:
    sup = model.supertype_of(cls)
    return sup.name if sup else "XtumlObject"


def class_declaration(model: Model, cls: XtClass) -> str:
    abstract = "abstract " if cls.is_abstract else ""
    return f"public {abstract}class {cls.name} extends {superclass_name(model, cls)}"


def setup_statements(model: Model) -> List[str]:
    """Pemanggilan Relationships.defineGeneralization(...) untuk ModelSetup.init()."""
    out: List[str] = []
    for r in model.relationships:
        if r.kind == "generalization":
            subs = ", ".join(f"{s}.class" for s in r.subtypes)
            out.append(f'Relationships.defineGeneralization("{r.rel_id}", {r.supertype}.class, {subs});')
    return out


def describe(model: Model, cls: XtClass) -> List[str]:
    out: List[str] = []
    for r in model.relationships:
        if r.kind != "generalization":
            continue
        if r.supertype == cls.name:
            out.append(f"{r.rel_id}: {cls.name} adalah supertype dari {', '.join(r.subtypes)}")
        elif cls.name in r.subtypes:
            out.append(f"{r.rel_id}: {cls.name} adalah subtype dari {r.supertype}")
    return out