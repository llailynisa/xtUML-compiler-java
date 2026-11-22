"""Generator file enum Java dari EnumType (SlotStatus -> SlotStatus.java)."""
from __future__ import annotations

from ..ir.model import EnumType, Model


def generate_enum(model: Model, enum: EnumType) -> str:
    values = ",\n".join(f"    {v}" for v in enum.values)
    return (f"package {model.package};\n\n"
            f"/** Enumerated type xtUML: {enum.name} */\n"
            f"public enum {enum.name} {{\n{values};\n}}\n")