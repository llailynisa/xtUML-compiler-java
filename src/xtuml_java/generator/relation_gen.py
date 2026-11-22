"""Relasi binary & association class: komentar dokumentasi dan ModelSetup.java."""
from __future__ import annotations

from typing import List

from ..ir.model import Model, Relationship, XtClass
from . import generalization_gen


def _end(r: Relationship, i: int) -> str:
    e = r.ends[i]
    return f"{e.class_name} ({e.multiplicity})"


def describe_relationship(r: Relationship) -> str:
    if r.kind == "generalization":
        return f"{r.rel_id}: generalisasi {r.supertype} <- {', '.join(r.subtypes)}"
    parts = []
    for i in (0, 1):
        phrase = r.ends[i].phrase
        parts.append(_end(r, i) + (' "' + phrase + '"' if phrase else ""))
    s = f"{r.rel_id}: {parts[0]} -- {parts[1]}"
    if r.assoc_class:
        s += f" [association class {r.assoc_class}]"
    return s


def relationship_comments(model: Model, cls: XtClass) -> List[str]:
    out: List[str] = []
    for r in model.relationships:
        if r.kind == "generalization":
            continue
        names = {e.class_name for e in r.ends} | ({r.assoc_class} if r.assoc_class else set())
        if cls.name in names:
            out.append(describe_relationship(r))
    out.extend(generalization_gen.describe(model, cls))
    return out


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def generate_model_setup(model: Model) -> str:
    body: List[str] = []
    for r in model.relationships:
        if r.kind == "generalization":
            continue
        a, b = r.ends
        args = (f'"{r.rel_id}", {a.class_name}.class, "{a.multiplicity}", {_q(a.phrase)}, '
                f'{b.class_name}.class, "{b.multiplicity}", {_q(b.phrase)}')
        if r.kind == "associative":
            body.append(f"Relationships.defineAssociative({args}, {r.assoc_class}.class);")
        else:
            body.append(f"Relationships.defineBinary({args});")
    body.extend(generalization_gen.setup_statements(model))
    inner = "\n".join(f"        {s}" for s in body)
    return (f"package {model.package};\n\n"
            "/** Inisialisasi runtime: mereset state dan mendaftarkan seluruh relasi model. */\n"
            "public final class ModelSetup {\n"
            "    private ModelSetup() {\n    }\n\n"
            "    public static void init() {\n"
            "        Store.reset();\n"
            "        Runtime.reset();\n"
            "        Relationships.reset();\n"
            f"{inner}\n"
            "    }\n}\n")