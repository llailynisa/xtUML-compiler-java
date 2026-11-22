"""Unit tests untuk penerjemah OAL (expressions.py, statements.py, translator.py)."""
from __future__ import annotations

from pathlib import Path

from xtuml_java.ir.model import INTEGER, STRING, TypeRef
from xtuml_java.loader.json_loader import load_from_file
from xtuml_java.oal.translator import translate_action

ROOT_DIR = Path(__file__).resolve().parents[1]
PARKING_GATE_PATH = ROOT_DIR / "models" / "parking_gate.json"


def _load_parking_model():
    res = load_from_file(PARKING_GATE_PATH)
    assert res.ok and res.model is not None
    return res.model


def test_oal_entry_gate_handle_vehicle() -> None:
    """Menguji select instances, if not_empty, enum, create object, relate using, dan generate."""
    model = _load_parking_model()
    entry_cls = model.get_class("EntryGate")
    assert entry_cls is not None
    op = entry_cls.operations[0]

    res = translate_action(
        model,
        op.body,
        cls=entry_cls,
        params={p.name: p.type for p in op.params},
        return_type=op.return_type,
        kind="operation",
        indent=2,
    )

    assert res.todos == []
    code = "\n".join(res.lines)
    assert "ParkingSlot slot = Store.selectAny(ParkingSlot.class, selected -> (selected.getStatus() == SlotStatus.FREE));" in code
    assert "if (Ops.notEmpty(slot)) {" in code
    assert "slot.setStatus(SlotStatus.OCCUPIED);" in code
    assert "ParkingSession session = new ParkingSession();" in code
    assert 'Relationships.relate("R4", veh, slot, session);' in code
    assert 'Runtime.generate(this, new Event("VehicleDetected"));' in code


def test_oal_exit_gate_navigation_and_string_equality() -> None:
    """Menguji navigasi association class (related by) dan nested if."""
    model = _load_parking_model()
    exit_cls = model.get_class("ExitGate")
    assert exit_cls is not None
    op = exit_cls.operations[0]

    res = translate_action(
        model,
        op.body,
        cls=exit_cls,
        params={p.name: p.type for p in op.params},
        return_type=op.return_type,
        kind="operation",
        indent=2,
    )

    assert res.todos == []
    code = "\n".join(res.lines)
    assert 'ParkingSession session = Relationships.navigateOne(veh, "R4", ParkingSession.class, null);' in code
    assert 'ParkingSlot slot = Relationships.navigateOne(veh, "R4", ParkingSlot.class, null);' in code
    assert 'Runtime.generate(session, new Event("Exited"));' in code


def test_oal_state_action_rcvd_evt_and_string_eq() -> None:
    """Menguji pembacaan rcvd_evt.param dan perbandingan string via Ops.eq."""
    model = _load_parking_model()
    gate_cls = model.get_class("Gate")
    assert gate_cls is not None

    oal = [
        'if (self.gateId == "GATE-1" and rcvd_evt.code > 0)',
        '  self.isOpen = true;',
        'else',
        '  self.isOpen = false;',
        'end if;',
    ]
    res = translate_action(
        model,
        oal,
        cls=gate_cls,
        params={"code": INTEGER},
        kind="state",
        indent=2,
    )

    assert res.todos == []
    code = "\n".join(res.lines)
    assert 'Ops.eq(this.getGateId(), "GATE-1")' in code
    assert '((Integer) rcvd_evt.get("code")) > 0' in code
    assert "this.setIsOpen(Ops.bool(true));" in code


def test_oal_unknown_statement_falls_back_to_todo_comment() -> None:
    """Baris OAL yang tidak dikenali menghasilkan komentar // TODO tanpa memicu crash."""
    model = _load_parking_model()
    lot_cls = model.get_class("ParkingLot")
    assert lot_cls is not None

    oal = [
        'self.name = "Central";',
        "invoke magic_unsupported_syntax(123);",
        "self.capacity = 100;",
    ]
    res = translate_action(model, oal, cls=lot_cls, kind="operation", indent=2)

    assert len(res.todos) == 1
    assert "invoke magic_unsupported_syntax(123);" in res.todos[0]
    code = "\n".join(res.lines)
    assert 'this.setName("Central");' in code
    assert "// TODO: invoke magic_unsupported_syntax(123);" in code
    assert "this.setCapacity(100);" in code