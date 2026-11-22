"""Unit tests untuk loader/json_loader.py dan loader/validator.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from xtuml_java.loader.json_loader import load_from_file, load_from_text
from xtuml_java.loader.validator import ModelValidationError

ROOT_DIR = Path(__file__).resolve().parents[1]
PARKING_GATE_PATH = ROOT_DIR / "models" / "parking_gate.json"


def test_load_parking_gate_example_valid() -> None:
    """Memastikan models/parking_gate.json berhasil dimuat ke IR tanpa error."""
    result = load_from_file(PARKING_GATE_PATH)

    assert result.ok is True
    assert result.errors == []
    assert result.model is not None

    model = result.model
    assert model.package == "parking"
    assert len(model.enums) == 2
    assert len(model.classes) == 7
    assert len(model.relationships) == 4
    assert len(model.scenario) > 0

    # Cek kelas abstrak & state machine Gate
    gate = model.get_class("Gate")
    assert gate is not None
    assert gate.is_abstract is True
    assert gate.state_machine is not None
    assert gate.state_machine.initial == "Closed"
    assert len(gate.state_machine.states) == 4
    assert len(gate.state_machine.transitions) == 4

    # Cek lookup via key_letters
    veh = model.class_by_key("VEH")
    assert veh is not None
    assert veh.name == "Vehicle"

    # Cek inheritance-aware helpers
    entry = model.get_class("EntryGate")
    assert entry is not None
    assert model.supertype_of(entry) == gate
    assert len(model.all_attributes(entry)) == 2


def test_invalid_json_syntax() -> None:
    """JSON dengan sintaks rusak menghasilkan error lokasi baris & kolom tanpa crash."""
    bad_json = '{"package": "demo", "classes": [}'
    result = load_from_text(bad_json)

    assert result.ok is False
    assert result.model is None
    assert len(result.errors) == 1
    assert "line" in result.errors[0].path
    assert "JSON tidak valid" in result.errors[0].message


def test_non_object_root() -> None:
    """Root JSON bukan dictionary menghasilkan error pada path '$'."""
    result = load_from_text('["not", "an", "object"]')

    assert result.ok is False
    assert result.model is None
    assert result.errors[0].path == "$"


def test_validation_errors_with_specific_paths() -> None:
    """Input JSON dengan berbagai kesalahan skema melaporkan daftar error ber-path spesifik."""
    broken_model = {
        "package": "class",  # keyword Java -> invalid
        "enums": [
            {"name": "Status", "values": []},  # values kosong -> invalid
            {"name": "String", "values": ["A", "A"]},  # reserved name & duplikat nilai
        ],
        "classes": [
            {
                "name": "Order",
                "key_letters": "ORD",
                "attributes": [
                    {"name": "id", "type": "unknown_type"},  # tipe tidak valid
                    {"name": "class", "type": "string"},  # getter getClass() reserved
                    {"name": "state", "type": "enum:MissingEnum"},  # enum tidak ada
                ],
                "operations": [
                    {
                        "name": "dispatch",  # nama operasi reserved
                        "params": [{"name": "1bad", "type": "inst_ref:GhostClass"}],
                        "return_type": "void",
                    }
                ],
                "state_machine": {
                    "initial": "NonExistentState",
                    "states": [{"name": "Idle", "action": []}],
                    "events": [{"name": "Start", "params": []}],
                    "transitions": [
                        {"source": "Idle", "event": "UnknownEvent", "target": "BadTarget"}
                    ],
                },
            }
        ],
        "relationships": [
            {
                "rel_id": "R1",
                "kind": "binary",
                "ends": [
                    {"class_name": "Order", "multiplicity": "5..2"},  # batas atas < batas bawah
                    {"class_name": "GhostClass", "multiplicity": "1"},  # kelas tidak ada
                ],
            },
            {
                "rel_id": "R2",
                "kind": "generalization",
                "supertype": "Order",
                "subtypes": ["Order"],  # subtype == supertype
            },
        ],
    }

    result = load_from_text(json.dumps(broken_model))

    assert result.ok is False
    assert result.model is None

    paths = {e.path for e in result.errors}
    assert "package" in paths
    assert "enums[0].values" in paths
    assert "enums[1].name" in paths
    assert "enums[1].values[1]" in paths
    assert "classes[0].attributes[0].type" in paths
    assert "classes[0].attributes[1].name" in paths
    assert "classes[0].attributes[2].type" in paths
    assert "classes[0].operations[0].name" in paths
    assert "classes[0].operations[0].params[0].name" in paths
    assert "classes[0].operations[0].params[0].type" in paths
    assert "classes[0].state_machine.initial" in paths
    assert "classes[0].state_machine.transitions[0].event" in paths
    assert "classes[0].state_machine.transitions[0].target" in paths
    assert "relationships[0].ends[0].multiplicity" in paths
    assert "relationships[0].ends[1].class_name" in paths
    assert "relationships[1].subtypes[0]" in paths


def test_default_key_letters_auto_generated() -> None:
    """Jika key_letters tidak diisi di JSON, loader otomatis menghasilkan inisial unik."""
    minimal = {
        "package": "demo",
        "classes": [
            {"name": "UserAccount"},
            {"name": "UserAdmin"},
        ],
    }
    result = load_from_text(json.dumps(minimal))

    assert result.ok is True
    assert result.model is not None
    c1 = result.model.get_class("UserAccount")
    c2 = result.model.get_class("UserAdmin")
    assert c1 is not None and c2 is not None
    assert c1.key_letters == "UA"
    assert c2.key_letters == "UA2"


def test_load_missing_file() -> None:
    """Membaca file yang tidak ada mengembalikan LoadResult gagal tanpa crash."""
    result = load_from_file(ROOT_DIR / "models" / "tidak_ada.json")

    assert result.ok is False
    assert result.model is None
    assert len(result.errors) == 1
    assert isinstance(result.errors[0], ModelValidationError)