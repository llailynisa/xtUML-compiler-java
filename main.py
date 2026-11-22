#!/usr/bin/env python3
"""Titik masuk xtuml2java.

  python main.py                      -> GUI Tkinter
  python main.py gui                  -> GUI Tkinter
  python main.py validate model.json  -> validasi
  python main.py generate model.json -o out --diagrams png
  python main.py run model.json       -> generate + javac + java
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from xtuml_java.cli import main as cli_main  # noqa: E402


def main() -> int:
    if len(sys.argv) == 1:
        return cli_main(["gui"])
    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())