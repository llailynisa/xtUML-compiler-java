"""Emitter: merangkai seluruh file Java dalam satu package (in-memory), lalu menulisnya ke disk bila diminta."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Union

from ..ir.model import Model
from . import class_gen, enum_gen, main_gen, relation_gen

RUNTIME_DIR = Path(__file__).parent / "runtime"
RUNTIME_FILES = ["XtumlObject", "Event", "Runtime", "Store", "Relationships", "Multiplicity",
                 "CardinalityViolationException", "Ops"]


@dataclass
class GeneratedProject:
    package: str
    files: Dict[str, str] = field(default_factory=dict)  # "Nama.java" -> isi (urutan penyisipan dipertahankan)
    todos: List[str] = field(default_factory=list)       # OAL yang tidak dapat diterjemahkan


def runtime_sources(package: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for name in RUNTIME_FILES:
        text = (RUNTIME_DIR / f"{name}.java").read_text(encoding="utf-8")
        text = text.replace("package xtuml_java.generator.runtime;", f"package {package};", 1)
        out[f"{name}.java"] = text.replace("package xtuml.runtime;", f"package {package};", 1)
    return out


def generate_project(model: Model) -> GeneratedProject:
    """Satu input model -> satu package Java terpadu (enum, class, relasi, state machine, runtime, Main)."""
    proj = GeneratedProject(model.package)
    for e in model.enums:
        proj.files[f"{e.name}.java"] = enum_gen.generate_enum(model, e)
    for c in model.classes:
        proj.files[f"{c.name}.java"] = class_gen.generate_class(model, c, proj.todos)
    proj.files["ModelSetup.java"] = relation_gen.generate_model_setup(model)
    proj.files["Main.java"] = main_gen.generate_main(model, proj.todos)
    proj.files.update(runtime_sources(model.package))
    return proj


def write_project(project: GeneratedProject, out_dir: Union[str, Path]) -> List[Path]:
    """Menulis *.java ke <out_dir>/<package>/ (dipanggil tombol Simpan GUI atau mode CLI)."""
    target = Path(out_dir).joinpath(*project.package.split("."))
    target.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for name, code in project.files.items():
        p = target / name
        p.write_text(code, encoding="utf-8", newline="\n")
        written.append(p)
    return written