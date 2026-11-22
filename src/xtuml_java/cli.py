"""Antarmuka CLI untuk mengompilasi model xtUML (JSON) menjadi proyek Java 17."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from xtuml_java.generator.emitter import generate_project, write_project
from xtuml_java.loader.json_loader import load_from_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xtuml2java",
        description="Compiler model xtUML (JSON) menjadi kode sumber Java 17.",
    )
    parser.add_argument(
        "model",
        type=Path,
        help="Path ke file model xtUML dalam format JSON (mis. models/parking_gate.json).",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("out"),
        help="Direktori root keluaran Java (default: out/).",
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Langsung kompilasi file .java yang dihasilkan menggunakan javac.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Kompilasi dengan javac lalu jalankan kelas Main menggunakan java.",
    )
    return parser


def run_cli(argv: Optional[List[str]] = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    if not raw_args or raw_args[0] == "gui":
        from .ui.app import run_gui
        return run_gui()

    parser = build_parser()
    args = parser.parse_args(raw_args)

    result = load_from_file(args.model)
    if not result.ok or result.model is None:
        print(f"[ERROR] Validasi model gagal ({len(result.errors)} masalah):", file=sys.stderr)
        for err in result.errors:
            print(f"  - [{err.severity.upper()}] {err.path}: {err.message}", file=sys.stderr)
        return 1

    model = result.model
    project = generate_project(model)
    written = write_project(project, args.out)
    pkg_dir = written[0].parent

    print(f"[OK] {len(written)} file Java berhasil dihasilkan di: {pkg_dir}")
    if project.todos:
        print(f"[INFO] Terdapat {len(project.todos)} baris OAL yang dikonversi menjadi // TODO:")
        for todo in project.todos:
            print(f"  * {todo}")

    if args.compile or args.run:
        java_files = [str(p) for p in written]
        print(f"[CMD] javac {' '.join(p.name for p in written)}")
        proc = subprocess.run(["javac", *java_files], capture_output=True, text=True)
        if proc.returncode != 0:
            print("[ERROR] Kompilasi javac gagal:", file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return proc.returncode
        print("[OK] Kompilasi javac berhasil (exit code 0).")

    if args.run:
        main_fqn = f"{model.package}.Main"
        print(f"[CMD] java -cp {args.out} {main_fqn}")
        proc = subprocess.run(["java", "-cp", str(args.out), main_fqn], capture_output=True, text=True)
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.returncode != 0:
            print("[ERROR] Eksekusi runtime Java gagal:", file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return proc.returncode

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    return run_cli(argv)
if __name__ == "__main__":
    raise SystemExit(run_cli())