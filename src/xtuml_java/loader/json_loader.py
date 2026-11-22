"""Parser JSON model xtUML menjadi Intermediate Representation (ir.model.Model)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..ir.model import (
    VOID,
    Attribute,
    EnumType,
    EventDef,
    Model,
    Multiplicity,
    Operation,
    Parameter,
    Relationship,
    RelEnd,
    State,
    StateMachine,
    Transition,
    TypeRef,
    XtClass,
)
from .validator import ModelValidationError, validate_raw_model


@dataclass
class LoadResult:
    model: Optional[Model] = None
    errors: List[ModelValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.model is not None and not any(e.severity == "error" for e in self.errors)


def _default_key_letters(class_name: str) -> str:
    caps = "".join(re.findall(r"[A-Z]", class_name))
    return caps if len(caps) >= 2 else class_name[:3].upper()


def _parse_oal_lines(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(line) for line in raw]
    if isinstance(raw, str):
        return [line for line in raw.splitlines() if line.strip()]
    return []


def _parse_params(raw_params: Any) -> List[Parameter]:
    out: List[Parameter] = []
    for p in raw_params or []:
        out.append(Parameter(name=p["name"], type=TypeRef.parse(p["type"])))
    return out


def _build_ir(data: Dict[str, Any]) -> Model:
    enums = [
        EnumType(name=e["name"], values=list(e["values"]))
        for e in data.get("enums", [])
    ]

    classes: List[XtClass] = []
    used_keys: set[str] = set()

    for c in data.get("classes", []):
        cname = c["name"]
        kl = c.get("key_letters")
        if not kl:
            base_kl = _default_key_letters(cname)
            kl = base_kl
            idx = 2
            while kl in used_keys:
                kl = f"{base_kl}{idx}"
                idx += 1
        used_keys.add(kl)

        attrs = [
            Attribute(name=a["name"], type=TypeRef.parse(a["type"]))
            for a in c.get("attributes", [])
        ]

        ops = [
            Operation(
                name=op["name"],
                params=_parse_params(op.get("params")),
                return_type=TypeRef.parse(op["return_type"]) if op.get("return_type") else VOID,
                is_abstract=bool(op.get("is_abstract", False)),
                body=_parse_oal_lines(op.get("body")),
            )
            for op in c.get("operations", [])
        ]

        sm_obj: Optional[StateMachine] = None
        sm_raw = c.get("state_machine")
        if sm_raw is not None:
            states: List[State] = []
            for st in sm_raw.get("states", []):
                if isinstance(st, dict):
                    states.append(State(name=st["name"], action=_parse_oal_lines(st.get("action"))))
                else:
                    states.append(State(name=str(st), action=[]))

            events: List[EventDef] = []
            for ev in sm_raw.get("events", []):
                if isinstance(ev, dict):
                    events.append(EventDef(name=ev["name"], params=_parse_params(ev.get("params"))))
                else:
                    events.append(EventDef(name=str(ev), params=[]))

            transitions = [
                Transition(
                    source=tr.get("source") or tr["from"],
                    event=tr["event"],
                    target=tr.get("target") or tr["to"],
                )
                for tr in sm_raw.get("transitions", [])
            ]

            sm_obj = StateMachine(
                initial=sm_raw["initial"],
                states=states,
                events=events,
                transitions=transitions,
            )

        classes.append(
            XtClass(
                name=cname,
                key_letters=kl,
                is_abstract=bool(c.get("is_abstract", False)),
                attributes=attrs,
                operations=ops,
                state_machine=sm_obj,
            )
        )

    relationships: List[Relationship] = []
    for r in data.get("relationships", []):
        rid = r.get("rel_id") or r["id"]
        kind = r["kind"]
        ends = [
            RelEnd(
                class_name=e.get("class_name") or e["class"],
                multiplicity=Multiplicity.parse(e["multiplicity"]),
                phrase=e.get("phrase", ""),
            )
            for e in r.get("ends", [])
        ]
        relationships.append(
            Relationship(
                rel_id=rid,
                kind=kind,
                ends=ends,
                assoc_class=r.get("assoc_class"),
                supertype=r.get("supertype"),
                subtypes=list(r.get("subtypes", [])),
            )
        )

    return Model(
        package=data["package"],
        enums=enums,
        classes=classes,
        relationships=relationships,
        scenario=_parse_oal_lines(data.get("scenario")),
    )


def load_from_text(text: str) -> LoadResult:
    """Mem-parse string JSON, memvalidasi skema, dan mengembalikan LoadResult."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as ex:
        return LoadResult(
            model=None,
            errors=[ModelValidationError(f"line {ex.lineno}, col {ex.colno}", f"JSON tidak valid: {ex.msg}")],
        )

    errors = validate_raw_model(data)
    if any(e.severity == "error" for e in errors):
        return LoadResult(model=None, errors=errors)

    try:
        model = _build_ir(data)
    except Exception as ex:
        errors.append(ModelValidationError("$", f"Gagal membangun IR: {ex}"))
        return LoadResult(model=None, errors=errors)

    return LoadResult(model=model, errors=errors)


def load_from_file(path: Union[str, Path]) -> LoadResult:
    """Membaca file JSON dari disk lalu memanggil load_from_text."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as ex:
        return LoadResult(model=None, errors=[ModelValidationError(str(p), f"Gagal membaca file: {ex}")])
    return load_from_text(text)

def load_model(source: Union[str, Path]) -> Model:
    """Wrapper kompatibilitas untuk test_generators.py: menerima path file atau string JSON dan mengembalikan Model."""
    p = Path(source) if isinstance(source, Path) or (
        isinstance(source, str) and not source.lstrip().startswith("{")
    ) else None

    res = load_from_file(p) if p is not None else load_from_text(str(source))
    if not res.ok or res.model is None:
        msgs = "; ".join(f"[{e.path}] {e.message}" for e in res.errors)
        raise ValueError(f"Model tidak valid: {msgs}")
    return res.model