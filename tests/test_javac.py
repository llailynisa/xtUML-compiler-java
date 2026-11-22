"""End-to-end tests: kompilasi hasil generate ke bytecode Java (javac) & eksekusi runtime."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from xtuml_java.cli import run_cli
from xtuml_java.generator.emitter import generate_project, write_project
from xtuml_java.loader.json_loader import load_from_file, load_from_text

ROOT_DIR = Path(__file__).resolve().parents[1]
PARKING_GATE_PATH = ROOT_DIR / "models" / "parking_gate.json"

HAS_JDK = shutil.which("javac") is not None and shutil.which("java") is not None


@pytest.mark.skipif(not HAS_JDK, reason="JDK (javac/java) tidak tersedia di PATH")
def test_parking_gate_compiles_and_runs_end_to_end(tmp_path: Path) -> None:
    """models/parking_gate.json -> generate Java -> javac -> java parking.Main."""
    out_dir = tmp_path / "out"
    exit_code = run_cli([str(PARKING_GATE_PATH), "-o", str(out_dir), "--compile", "--run"])
    assert exit_code == 0

    pkg_dir = out_dir / "parking"
    expected_files = [
        "SlotStatus.java",
        "VehicleType.java",
        "ParkingLot.java",
        "ParkingSlot.java",
        "Gate.java",
        "EntryGate.java",
        "ExitGate.java",
        "Vehicle.java",
        "ParkingSession.java",
        "ModelSetup.java",
        "Main.java",
    ]
    for fname in expected_files:
        assert (pkg_dir / fname).exists(), f"File {fname} tidak dihasilkan"
        assert (pkg_dir / fname.replace(".java", ".class")).exists(), f"Bytecode {fname} tidak terbentuk"


@pytest.mark.skipif(not HAS_JDK, reason="JDK (javac/java) tidak tersedia di PATH")
def test_cardinality_violation_throws_exception_at_runtime(tmp_path: Path) -> None:
    """Memastikan pelanggaran batas atas multiplisitas melempar CardinalityViolationException."""
    model_data = {
        "package": "cardtest",
        "classes": [
            {"name": "Owner", "key_letters": "OWN", "attributes": [{"name": "name", "type": "string"}]},
            {"name": "Pet", "key_letters": "PET", "attributes": [{"name": "name", "type": "string"}]},
        ],
        "relationships": [
            {
                "rel_id": "R1",
                "kind": "binary",
                "ends": [
                    {"class_name": "Owner", "multiplicity": "1", "phrase": "owns"},
                    {"class_name": "Pet", "multiplicity": "1", "phrase": "owned by"},
                ],
            }
        ],
        "scenario": [
            "create object instance o of OWN;",
            "create object instance p1 of PET;",
            "create object instance p2 of PET;",
            "relate o to p1 across R1;",
            "relate o to p2 across R1;",
        ],
    }

    res = load_from_text(json.dumps(model_data))
    assert res.ok and res.model is not None

    out_dir = tmp_path / "out"
    proj = generate_project(res.model)
    written = write_project(proj, out_dir)

    cproc = subprocess.run(["javac", *[str(p) for p in written]], capture_output=True, text=True)
    assert cproc.returncode == 0, cproc.stderr

    rproc = subprocess.run(["java", "-cp", str(out_dir), "cardtest.Main"], capture_output=True, text=True)
    assert rproc.returncode != 0
    assert "Pelanggaran kardinalitas" in rproc.stdout or "CardinalityViolationException" in rproc.stderr

@pytest.mark.skipif(not HAS_JDK, reason="JDK (javac/java) tidak tersedia di PATH")
def test_unrecognized_oal_todo_still_passes_javac(tmp_path: Path) -> None:
    """Baris OAL yang tidak dikenal menghasilkan // TODO dan tetap lolos kompilasi javac."""
    model_data = {
        "package": "todotest",
        "classes": [
            {
                "name": "Box",
                "key_letters": "BOX",
                "attributes": [{"name": "label", "type": "string"}],
                "operations": [
                    {
                        "name": "doWork",
                        "return_type": "void",
                        "body": [
                            'self.label = "OK";',
                            "unsupported_custom_command x y z;",
                        ],
                    }
                ],
            }
        ],
        "scenario": [
            "create object instance b of BOX;",
            "b.doWork();",
        ],
    }

    res = load_from_text(json.dumps(model_data))
    assert res.ok and res.model is not None

    out_dir = tmp_path / "out"
    proj = generate_project(res.model)
    assert len(proj.todos) == 1

    written = write_project(proj, out_dir)
    cproc = subprocess.run(["javac", *[str(p) for p in written]], capture_output=True, text=True)
    assert cproc.returncode == 0, cproc.stderr