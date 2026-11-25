"""Generator Main.java untuk mengeksekusi skenario model xtUML dan event loop Runtime."""
from __future__ import annotations

from typing import List, Optional

from ..ir.model import Model
from ..oal.translator import translate_action


def generate_main(model: Model, todos: Optional[List[str]] = None) -> str:
    """Menghasilkan kode sumber lengkap Main.java dalam package model."""
    res = translate_action(
        model,
        model.scenario,
        cls=None,
        params=None,
        kind="scenario",
        indent=3,
    )
    if todos is not None:
        todos.extend(f"Main.scenario: {t}" for t in res.todos)

    lines: List[str] = [
        f"package {model.package};",
        "",
        "/**",
        f" * Titik masuk simulasi model xtUML: {model.package}",
        " */",
        "public class Main {",
        "    public static void main(String[] args) {",
        "        ModelSetup.init();",
        "        try {",
    ]

    if res.lines:
        lines.extend(res.lines)
    else:
        lines.append('            Ops.logInfo("Tidak ada skenario awal pada model.");')

    lines.extend([
        "",
        "            Runtime.run();",
        '            Ops.logInfo("Simulasi selesai. Total instance hidup: " + Store.liveInstances().size());',
        "        } catch (CardinalityViolationException ex) {",
        '            Ops.logFailure("Pelanggaran kardinalitas: " + ex.getMessage());',
        "            System.exit(1);",
        "        }",
        "    }",
        "}",
    ])

    imports: List[str] = []
    if any("List<" in line for line in lines):
        imports.append("import java.util.List;")
    if any("ArrayList<" in line for line in lines):
        imports.append("import java.util.ArrayList;")
    if imports:
        lines[2:2] = imports + [""]

    return "\n".join(lines) + "\n"