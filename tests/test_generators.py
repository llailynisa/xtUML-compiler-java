"""Tes generator: enum, class, relasi, state machine, emitter."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import tempfile
import unittest

from xtuml_java.generator.emitter import RUNTIME_FILES, generate_project, write_project
from xtuml_java.loader.json_loader import load_model

MODEL = load_model(ROOT / "models" / "parking_gate.json")
PROJECT = generate_project(MODEL)
F = PROJECT.files


class Generators(unittest.TestCase):
    def test_file_set(self):
        expected = {"SlotStatus.java", "VehicleType.java", "ParkingLot.java", "ParkingSlot.java", "Gate.java",
                    "EntryGate.java", "ExitGate.java", "Vehicle.java", "ParkingSession.java", "ModelSetup.java", "Main.java"}
        expected |= {f"{n}.java" for n in RUNTIME_FILES}
        self.assertEqual(set(F), expected)
        self.assertEqual(PROJECT.todos, [])

    def test_all_files_share_package(self):
        for name, code in F.items():
            self.assertTrue(code.startswith("package parking;"), name)

    def test_enum(self):
        self.assertIn("public enum SlotStatus {\n    FREE,\n    OCCUPIED,\n    RESERVED;\n}", F["SlotStatus.java"])

    def test_class_structure(self):
        slot = F["ParkingSlot.java"]
        self.assertIn("public class ParkingSlot extends XtumlObject", slot)
        self.assertIn("private SlotStatus status = null;", slot)
        self.assertIn("public SlotStatus getStatus()", slot)
        self.assertIn("public void setStatus(SlotStatus value)", slot)
        self.assertIn('return "SLOT";', slot)

    def test_generalization(self):
        self.assertIn("public abstract class Gate extends XtumlObject", F["Gate.java"])
        self.assertIn("public abstract void handleVehicle(Vehicle veh);", F["Gate.java"])
        self.assertIn("public class EntryGate extends Gate", F["EntryGate.java"])
        self.assertIn("@Override\n    public void handleVehicle(Vehicle veh)", F["EntryGate.java"])

    def test_model_setup_registers_relations_with_multiplicity(self):
        s = F["ModelSetup.java"]
        self.assertIn('Relationships.defineBinary("R1", ParkingLot.class, "1", "contains", ParkingSlot.class, "0..*", "is in");', s)
        self.assertIn('"R2", ParkingLot.class, "1", "operates", Gate.class, "1..*", "operated by"', s)
        self.assertIn('Relationships.defineAssociative("R4", Vehicle.class, "0..*"', s)
        self.assertIn("ParkingSession.class);", s)
        self.assertIn('Relationships.defineGeneralization("R5", Gate.class, EntryGate.class, ExitGate.class);', s)

    def test_state_machine_members(self):
        g = F["Gate.java"]
        for needle in ("public enum State {", 'CLOSED("Closed"),', "protected State currentState = State.CLOSED;",
                       "public void dispatch(Event event)", "private void enter(State next, Event rcvd_evt)",
                       "private void action_Opening(Event rcvd_evt)", 'event.getName().equals("VehicleDetected")'):
            self.assertIn(needle, g)
        self.assertNotIn("dispatch", F["EntryGate.java"])  # mewarisi dari Gate

    def test_runtime_package_rewritten(self):
        for n in RUNTIME_FILES:
            self.assertIn("package parking;", F[f"{n}.java"])
            self.assertNotIn("xtuml.runtime", F[f"{n}.java"])

    def test_main_contains_scenario_and_violation_handler(self):
        m = F["Main.java"]
        self.assertIn("ModelSetup.init();", m)
        self.assertIn("catch (CardinalityViolationException ex)", m)
        self.assertIn("Runtime.run();", m)

    def test_generation_is_in_memory_until_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = generate_project(MODEL)
            self.assertEqual(list(__import__("pathlib").Path(tmp).iterdir()), [])
            written = write_project(proj, tmp)
            self.assertEqual(len(written), len(proj.files))
            self.assertTrue((__import__("pathlib").Path(tmp) / "parking" / "Main.java").exists())

    def test_nested_package_directory(self):
        import dataclasses
        with tempfile.TemporaryDirectory() as tmp:
            proj = generate_project(dataclasses.replace(MODEL, package="com.kampus.parkir"))
            write_project(proj, tmp)
            self.assertTrue((__import__("pathlib").Path(tmp) / "com" / "kampus" / "parkir" / "Gate.java").exists())

    def test_java_keyword_attribute_is_escaped(self):
        from xtuml_java.loader.json_loader import load_from_text
        res = load_from_text('{"package":"p","classes":[{"name":"A","attributes":[{"name":"default","type":"integer"}]}]}')
        code = generate_project(res.model).files["A.java"]
        self.assertIn("private int default_ = 0;", code)
        self.assertIn("public int getDefault()", code)

    def test_attribute_clashing_with_object_methods_is_rejected(self):
        from xtuml_java.loader.json_loader import load_from_text
        for name in ("class", "instanceId", "keyLetters", "currentState"):
            res = load_from_text('{"package":"p","classes":[{"name":"A","attributes":[{"name":"%s","type":"integer"}]}]}' % name)
            self.assertFalse(res.ok, name)

    def test_operation_clashing_with_builtin_is_rejected(self):
        from xtuml_java.loader.json_loader import load_from_text
        for name in ("dispatch", "toString", "hashCode", "enter"):
            res = load_from_text('{"package":"p","classes":[{"name":"A","operations":[{"name":"%s"}]}]}' % name)
            self.assertFalse(res.ok, name)


if __name__ == "__main__":
    unittest.main()