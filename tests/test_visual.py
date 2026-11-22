"""Unit tests untuk visual/state_diagram.py."""
from __future__ import annotations

from pathlib import Path

from xtuml_java.ir.model import EventDef, State, StateMachine, Transition
from xtuml_java.loader.json_loader import load_from_file
from xtuml_java.visual.layout import DrawList, Ellipse, Line, Rect, Text
from xtuml_java.visual.state_diagram import build_state_diagram

ROOT_DIR = Path(__file__).resolve().parents[1]
PARKING_GATE_PATH = ROOT_DIR / "models" / "parking_gate.json"


def _texts(dl: DrawList) -> list[str]:
    return [it.text for it in dl.items if isinstance(it, Text)]


def test_build_state_diagram_for_parking_gate() -> None:
    """Memastikan State Diagram Gate dan ParkingSession dirender lengkap ke DrawList."""
    res = load_from_file(PARKING_GATE_PATH)
    assert res.ok and res.model is not None

    gate_cls = res.model.get_class("Gate")
    assert gate_cls is not None and gate_cls.state_machine is not None

    dl = build_state_diagram(gate_cls.state_machine, gate_cls.name)
    assert isinstance(dl, DrawList)
    assert dl.width > 0
    assert dl.height > 0

    # Pastikan initial marker (Ellipse), state boxes (Rect), dan panah (Line) tergambar
    assert any(isinstance(it, Ellipse) for it in dl.items)
    assert any(isinstance(it, Rect) for it in dl.items)
    assert any(isinstance(it, Line) for it in dl.items)

    labels = _texts(dl)
    assert "State Machine: Gate" in labels
    for state_name in ("Closed", "Opening", "Open", "Closing"):
        assert state_name in labels
    for event_name in ("VehicleDetected", "BarrierUp", "VehicleCleared", "BarrierDown"):
        assert event_name in labels


def test_build_state_diagram_self_transition_and_empty() -> None:
    """Menguji self-transition dan state machine kosong tanpa crash."""
    empty_dl = build_state_diagram(None, "EmptyClass")
    assert empty_dl.width > 0 and empty_dl.height > 0
    assert any("kosong" in t for t in _texts(empty_dl))

    sm = StateMachine(
        initial="Idle",
        states=[State("Idle", action=["self.count = 0;"])],
        events=[EventDef("Ping")],
        transitions=[Transition("Idle", "Ping", "Idle")],
    )
    dl = build_state_diagram(sm, "Worker")
    labels = _texts(dl)
    assert "Idle" in labels
    assert "Ping" in labels
    assert any("entry / self.count = 0;" in t for t in labels)