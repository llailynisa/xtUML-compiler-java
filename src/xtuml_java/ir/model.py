"""Intermediate Representation (IR) model xtUML.

Semua modul hilir (oal, generator, visual, ui) HANYA membaca objek-objek di file ini;
dilarang membaca JSON mentah. Berisi juga helper penamaan Java yang dipakai bersama.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Konstanta & helper penamaan Java (kontrak bersama)
# ---------------------------------------------------------------------------

JAVA_KEYWORDS: Set[str] = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class", "const",
    "continue", "default", "do", "double", "else", "enum", "extends", "final", "finally", "float",
    "for", "goto", "if", "implements", "import", "instanceof", "int", "interface", "long", "native",
    "new", "package", "private", "protected", "public", "return", "short", "static", "strictfp",
    "super", "switch", "synchronized", "this", "throw", "throws", "transient", "try", "void",
    "volatile", "while", "true", "false", "null", "var", "record", "yield", "_",
}

# Nama kelas runtime / hasil generate yang tidak boleh dipakai sebagai nama kelas model.
RESERVED_CLASS_NAMES: Set[str] = {
    "XtumlObject", "Event", "Runtime", "Store", "Relationships", "Multiplicity",
    "CardinalityViolationException", "Ops", "ModelSetup", "Main", "State",
    "String", "Object", "List", "ArrayList", "Integer", "Double", "Boolean", "Math", "System",
}

# Nama method yang sudah dipakai Object/XtumlObject/state machine: tidak boleh dihasilkan sebagai
# getter atribut maupun dipakai sebagai nama operasi.
RESERVED_GETTERS: Set[str] = {"getClass", "getInstanceId", "getKeyLetters", "getCurrentState"}
RESERVED_OPERATIONS: Set[str] = RESERVED_GETTERS | {
    "dispatch", "describe", "isDeleted", "markDeleted", "toString", "equals", "hashCode", "notify",
    "notifyAll", "wait", "clone", "finalize", "enter",
}

PRIMITIVE_TYPES = ("string", "integer", "boolean", "real")
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def safe_ident(name: str) -> str:
    """Nama variabel/parameter yang aman di Java (keyword diberi akhiran '_')."""
    return name + "_" if name in JAVA_KEYWORDS else name


def cap(name: str) -> str:
    return name[:1].upper() + name[1:]


def getter_name(attr: str) -> str:
    return "get" + cap(attr)


def setter_name(attr: str) -> str:
    return "set" + cap(attr)


def const_name(name: str) -> str:
    """CamelCase -> UPPER_SNAKE (Closed -> CLOSED, VehicleDetected -> VEHICLE_DETECTED)."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).upper()


# ---------------------------------------------------------------------------
# Tipe & multiplisitas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Multiplicity:
    lower: int
    upper: Optional[int]  # None = tak terbatas (*)

    @staticmethod
    def parse(text: str) -> "Multiplicity":
        t = str(text).strip()
        if t == "*":
            return Multiplicity(0, None)
        m = re.fullmatch(r"(\d+)(?:\.\.(\d+|\*))?", t)
        if not m:
            raise ValueError(f"multiplisitas tidak valid: {text!r}")
        lo = int(m.group(1))
        if m.group(2) is None:
            return Multiplicity(lo, lo)
        hi = None if m.group(2) == "*" else int(m.group(2))
        if hi is not None and hi < lo:
            raise ValueError(f"multiplisitas tidak valid (batas atas < batas bawah): {text!r}")
        return Multiplicity(lo, hi)

    def __str__(self) -> str:
        if self.upper == self.lower:
            return str(self.lower)
        return f"{self.lower}..{'*' if self.upper is None else self.upper}"


@dataclass(frozen=True)
class TypeRef:
    """kind: string|integer|boolean|real|enum|inst_ref|inst_ref_set|void"""
    kind: str
    target: Optional[str] = None  # nama enum, atau nama class / key letters

    @staticmethod
    def parse(text: str) -> "TypeRef":
        t = str(text).strip()
        if t in PRIMITIVE_TYPES or t == "void":
            return TypeRef(t)
        m = re.fullmatch(r"(enum|inst_ref_set|inst_ref):([A-Za-z_][A-Za-z0-9_]*)", t)
        if not m:
            raise ValueError(f"tipe tidak valid: {text!r}")
        return TypeRef(m.group(1), m.group(2))

    @property
    def is_primitive(self) -> bool:
        return self.kind in PRIMITIVE_TYPES

    def __str__(self) -> str:
        return self.kind if self.target is None else f"{self.kind}:{self.target}"


VOID = TypeRef("void")
STRING = TypeRef("string")
INTEGER = TypeRef("integer")
BOOLEAN = TypeRef("boolean")
REAL = TypeRef("real")


# ---------------------------------------------------------------------------
# Elemen model
# ---------------------------------------------------------------------------

@dataclass
class EnumType:
    name: str
    values: List[str]


@dataclass
class Attribute:
    name: str
    type: TypeRef


@dataclass
class Parameter:
    name: str
    type: TypeRef


@dataclass
class Operation:
    name: str
    params: List[Parameter] = field(default_factory=list)
    return_type: TypeRef = VOID
    is_abstract: bool = False
    body: List[str] = field(default_factory=list)  # baris OAL


@dataclass
class EventDef:
    name: str
    params: List[Parameter] = field(default_factory=list)


@dataclass
class State:
    name: str
    action: List[str] = field(default_factory=list)  # OAL entry action


@dataclass
class Transition:
    source: str
    event: str
    target: str


@dataclass
class StateMachine:
    initial: str
    states: List[State] = field(default_factory=list)
    events: List[EventDef] = field(default_factory=list)
    transitions: List[Transition] = field(default_factory=list)

    def state(self, name: str) -> Optional[State]:
        return next((s for s in self.states if s.name == name), None)

    def event(self, name: str) -> Optional[EventDef]:
        return next((e for e in self.events if e.name == name), None)


@dataclass
class XtClass:
    name: str
    key_letters: str
    is_abstract: bool = False
    attributes: List[Attribute] = field(default_factory=list)
    operations: List[Operation] = field(default_factory=list)
    state_machine: Optional[StateMachine] = None


@dataclass
class RelEnd:
    class_name: str
    multiplicity: Multiplicity
    phrase: str = ""


@dataclass
class Relationship:
    rel_id: str
    kind: str  # binary | associative | generalization
    ends: List[RelEnd] = field(default_factory=list)  # 2 ujung (binary/associative)
    assoc_class: Optional[str] = None
    supertype: Optional[str] = None
    subtypes: List[str] = field(default_factory=list)


@dataclass
class Model:
    package: str
    enums: List[EnumType] = field(default_factory=list)
    classes: List[XtClass] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    scenario: List[str] = field(default_factory=list)  # OAL untuk Main.java

    # ---- lookup -----------------------------------------------------------
    def get_class(self, name: str) -> Optional[XtClass]:
        return next((c for c in self.classes if c.name == name), None)

    def class_by_key(self, key: str) -> Optional[XtClass]:
        return next((c for c in self.classes if c.key_letters == key), None)

    def resolve_class(self, name_or_key: str) -> Optional[XtClass]:
        return self.get_class(name_or_key) or self.class_by_key(name_or_key)

    def get_enum(self, name: str) -> Optional[EnumType]:
        return next((e for e in self.enums if e.name == name), None)

    def get_relationship(self, rel_id: str) -> Optional[Relationship]:
        return next((r for r in self.relationships if r.rel_id == rel_id), None)

    # ---- generalisasi -----------------------------------------------------
    def supertype_of(self, cls: XtClass) -> Optional[XtClass]:
        for r in self.relationships:
            if r.kind == "generalization" and cls.name in r.subtypes:
                return self.get_class(r.supertype or "")
        return None

    def subtypes_of(self, cls: XtClass) -> List[XtClass]:
        out: List[XtClass] = []
        for r in self.relationships:
            if r.kind == "generalization" and r.supertype == cls.name:
                out.extend(c for c in (self.get_class(n) for n in r.subtypes) if c)
        return out

    def ancestors(self, cls: XtClass) -> List[XtClass]:
        """Dari supertype terdekat sampai root."""
        out: List[XtClass] = []
        cur = self.supertype_of(cls)
        seen: Set[str] = set()
        while cur is not None and cur.name not in seen:
            out.append(cur)
            seen.add(cur.name)
            cur = self.supertype_of(cur)
        return out

    def descendants(self, cls: XtClass) -> List[XtClass]:
        out: List[XtClass] = []
        for s in self.subtypes_of(cls):
            out.append(s)
            out.extend(self.descendants(s))
        return out

    def is_subtype_of(self, cls: XtClass, other: XtClass) -> bool:
        return cls.name == other.name or any(a.name == other.name for a in self.ancestors(cls))

    def all_attributes(self, cls: XtClass) -> List[Attribute]:
        """Atribut inheritance-aware (supertype dulu)."""
        out: List[Attribute] = []
        for a in reversed(self.ancestors(cls)):
            out.extend(a.attributes)
        out.extend(cls.attributes)
        return out

    def find_attribute(self, cls: XtClass, name: str) -> Optional[Attribute]:
        return next((a for a in self.all_attributes(cls) if a.name == name), None)

    def find_operation(self, cls: XtClass, name: str) -> Optional[Operation]:
        for c in [cls] + self.ancestors(cls):
            for op in c.operations:
                if op.name == name:
                    return op
        return None

    def state_machine_owner(self, cls: XtClass) -> Optional[XtClass]:
        """Kelas yang mendefinisikan state machine untuk cls (cls sendiri atau supertype)."""
        for c in [cls] + self.ancestors(cls):
            if c.state_machine is not None:
                return c
        return None

    def relationship_classes(self, rel: Relationship) -> Set[str]:
        names: Set[str] = {e.class_name for e in rel.ends}
        if rel.assoc_class:
            names.add(rel.assoc_class)
        if rel.supertype:
            names.add(rel.supertype)
        names.update(rel.subtypes)
        return names

    # ---- tipe -> Java -----------------------------------------------------
    def class_of_ref(self, t: TypeRef) -> Optional[XtClass]:
        if t.kind in ("inst_ref", "inst_ref_set") and t.target:
            return self.resolve_class(t.target)
        return None

    def java_type(self, t: TypeRef, boxed: bool = False) -> str:
        k = t.kind
        if k == "string":
            return "String"
        if k == "integer":
            return "Integer" if boxed else "int"
        if k == "boolean":
            return "Boolean" if boxed else "boolean"
        if k == "real":
            return "Double" if boxed else "double"
        if k == "void":
            return "void"
        if k == "enum":
            return t.target or "Object"
        c = self.class_of_ref(t)
        name = c.name if c else (t.target or "Object")
        return f"List<{name}>" if k == "inst_ref_set" else name

    def java_default(self, t: TypeRef) -> str:
        return {
            "string": '""', "integer": "0", "boolean": "false", "real": "0.0",
            "inst_ref_set": "new ArrayList<>()",
        }.get(t.kind, "null")
