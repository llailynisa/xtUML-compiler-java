"""Validator skema & semantik model xtUML (JSON) sebelum dipetakan ke IR."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set

from ..ir.model import (
    IDENT_RE,
    JAVA_KEYWORDS,
    RESERVED_CLASS_NAMES,
    RESERVED_GETTERS,
    RESERVED_OPERATIONS,
    Multiplicity,
    TypeRef,
    getter_name,
)


@dataclass
class ModelValidationError:
    path: str
    message: str
    severity: str = "error"  # "error" | "warning"


def _check_ident(name: Any, path: str, errors: List[ModelValidationError], label: str = "Nama") -> bool:
    if not isinstance(name, str) or not name.strip():
        errors.append(ModelValidationError(path, f"{label} wajib berupa string tidak kosong."))
        return False
    if not IDENT_RE.fullmatch(name):
        errors.append(ModelValidationError(path, f"{label} '{name}' harus berupa identifier valid (huruf/angka/underscore, tidak diawali angka)."))
        return False
    return True


def validate_raw_model(data: Any) -> List[ModelValidationError]:
    """Memvalidasi dictionary JSON mentah dan mengembalikan daftar ModelValidationError."""
    errors: List[ModelValidationError] = []

    if not isinstance(data, dict):
        return [ModelValidationError("$", "Root JSON harus berupa objek (dictionary).")]

    # 1. Validasi package
    pkg = data.get("package")
    if not isinstance(pkg, str) or not pkg.strip():
        errors.append(ModelValidationError("package", "Field 'package' wajib diisi string."))
    else:
        parts = pkg.split(".")
        for p in parts:
            if not IDENT_RE.fullmatch(p) or p in JAVA_KEYWORDS:
                errors.append(ModelValidationError("package", f"Nama package '{pkg}' mengandung segmen tidak valid '{p}'."))
                break

    # 2. Validasi enums
    enums_raw = data.get("enums", [])
    declared_enums: Set[str] = set()
    if not isinstance(enums_raw, list):
        errors.append(ModelValidationError("enums", "Field 'enums' harus berupa list."))
        enums_raw = []

    for i, e in enumerate(enums_raw):
        epath = f"enums[{i}]"
        if not isinstance(e, dict):
            errors.append(ModelValidationError(epath, "Elemen enum harus berupa objek."))
            continue
        ename = e.get("name")
        if _check_ident(ename, f"{epath}.name", errors, "Nama enum"):
            if ename in RESERVED_CLASS_NAMES:
                errors.append(ModelValidationError(f"{epath}.name", f"Nama enum '{ename}' bentrok dengan kelas runtime/Java."))
            elif ename in declared_enums:
                errors.append(ModelValidationError(f"{epath}.name", f"Duplikat nama enum '{ename}'."))
            else:
                declared_enums.add(ename)

        vals = e.get("values")
        if not isinstance(vals, list) or len(vals) == 0:
            errors.append(ModelValidationError(f"{epath}.values", "Enum wajib memiliki minimal 1 nilai pada 'values'."))
        else:
            seen_vals: Set[str] = set()
            for j, v in enumerate(vals):
                vpath = f"{epath}.values[{j}]"
                if _check_ident(v, vpath, errors, "Nilai enum"):
                    if v in seen_vals:
                        errors.append(ModelValidationError(vpath, f"Duplikat nilai enum '{v}'."))
                    seen_vals.add(v)

    # 3. Kumpulkan identitas kelas terlebih dahulu untuk cross-reference
    classes_raw = data.get("classes", [])
    declared_classes: Set[str] = set()
    declared_keys: Set[str] = set()
    if not isinstance(classes_raw, list) or len(classes_raw) == 0:
        errors.append(ModelValidationError("classes", "Model wajib memiliki minimal 1 kelas pada 'classes'."))
        classes_raw = []

    for i, c in enumerate(classes_raw):
        cpath = f"classes[{i}]"
        if not isinstance(c, dict):
            errors.append(ModelValidationError(cpath, "Elemen class harus berupa objek."))
            continue
        cname = c.get("name")
        if _check_ident(cname, f"{cpath}.name", errors, "Nama class"):
            if cname in RESERVED_CLASS_NAMES or cname in declared_enums:
                errors.append(ModelValidationError(f"{cpath}.name", f"Nama class '{cname}' sudah dipakai atau termasuk reserved name."))
            elif cname in declared_classes:
                errors.append(ModelValidationError(f"{cpath}.name", f"Duplikat nama class '{cname}'."))
            else:
                declared_classes.add(cname)

        kl = c.get("key_letters")
        if kl is not None:
            if _check_ident(kl, f"{cpath}.key_letters", errors, "Key letters"):
                if kl in declared_keys:
                    errors.append(ModelValidationError(f"{cpath}.key_letters", f"Duplikat key_letters '{kl}'."))
                declared_keys.add(kl)

    valid_class_refs = declared_classes | declared_keys

    def _validate_typeref(raw_type: Any, tpath: str, allow_void: bool = False) -> None:
        if not isinstance(raw_type, str) or not raw_type.strip():
            errors.append(ModelValidationError(tpath, "Tipe wajib berupa string."))
            return
        try:
            tr = TypeRef.parse(raw_type)
        except ValueError as ex:
            errors.append(ModelValidationError(tpath, str(ex)))
            return
        if tr.kind == "void" and not allow_void:
            errors.append(ModelValidationError(tpath, "Tipe 'void' hanya diizinkan sebagai return_type operasi."))
        elif tr.kind == "enum" and tr.target not in declared_enums:
            errors.append(ModelValidationError(tpath, f"Referensi enum '{tr.target}' tidak ditemukan di 'enums'."))
        elif tr.kind in ("inst_ref", "inst_ref_set") and tr.target not in valid_class_refs:
            errors.append(ModelValidationError(tpath, f"Referensi class '{tr.target}' tidak ditemukan di 'classes'."))

    # 4. Validasi detail tiap kelas (attributes, operations, state_machine)
    for i, c in enumerate(classes_raw):
        if not isinstance(c, dict):
            continue
        cpath = f"classes[{i}]"

        # Attributes
        attrs = c.get("attributes", [])
        if not isinstance(attrs, list):
            errors.append(ModelValidationError(f"{cpath}.attributes", "Field 'attributes' harus berupa list."))
            attrs = []
        seen_attrs: Set[str] = set()
        for j, a in enumerate(attrs):
            apath = f"{cpath}.attributes[{j}]"
            if not isinstance(a, dict):
                errors.append(ModelValidationError(apath, "Atribut harus berupa objek."))
                continue
            aname = a.get("name")
            if _check_ident(aname, f"{apath}.name", errors, "Nama atribut"):
                if aname in seen_attrs:
                    errors.append(ModelValidationError(f"{apath}.name", f"Duplikat atribut '{aname}'."))
                elif getter_name(aname) in RESERVED_GETTERS:
                    errors.append(ModelValidationError(f"{apath}.name", f"Getter '{getter_name(aname)}' bentrok dengan method bawaan."))
                seen_attrs.add(aname)
            _validate_typeref(a.get("type"), f"{apath}.type", allow_void=False)

        # Operations
        ops = c.get("operations", [])
        if not isinstance(ops, list):
            errors.append(ModelValidationError(f"{cpath}.operations", "Field 'operations' harus berupa list."))
            ops = []
        seen_ops: Set[str] = set()
        for j, op in enumerate(ops):
            opath = f"{cpath}.operations[{j}]"
            if not isinstance(op, dict):
                errors.append(ModelValidationError(opath, "Operasi harus berupa objek."))
                continue
            oname = op.get("name")
            if _check_ident(oname, f"{opath}.name", errors, "Nama operasi"):
                if oname in seen_ops:
                    errors.append(ModelValidationError(f"{opath}.name", f"Duplikat operasi '{oname}'."))
                elif oname in RESERVED_OPERATIONS:
                    errors.append(ModelValidationError(f"{opath}.name", f"Nama operasi '{oname}' bentrok dengan method bawaan."))
                seen_ops.add(oname)

            if "return_type" in op and op["return_type"] is not None:
                _validate_typeref(op["return_type"], f"{opath}.return_type", allow_void=True)

            params = op.get("params", [])
            if not isinstance(params, list):
                errors.append(ModelValidationError(f"{opath}.params", "Field 'params' harus berupa list."))
                params = []
            for k, p in enumerate(params):
                ppath = f"{opath}.params[{k}]"
                if not isinstance(p, dict):
                    errors.append(ModelValidationError(ppath, "Parameter harus berupa objek."))
                    continue
                _check_ident(p.get("name"), f"{ppath}.name", errors, "Nama parameter")
                _validate_typeref(p.get("type"), f"{ppath}.type", allow_void=False)

        # State Machine
        sm = c.get("state_machine")
        if sm is not None:
            smpath = f"{cpath}.state_machine"
            if not isinstance(sm, dict):
                errors.append(ModelValidationError(smpath, "Field 'state_machine' harus berupa objek."))
                continue

            states_raw = sm.get("states", [])
            events_raw = sm.get("events", [])
            trans_raw = sm.get("transitions", [])

            declared_states: Set[str] = set()
            if not isinstance(states_raw, list) or len(states_raw) == 0:
                errors.append(ModelValidationError(f"{smpath}.states", "State machine wajib memiliki minimal 1 state."))
            else:
                for j, st in enumerate(states_raw):
                    stpath = f"{smpath}.states[{j}]"
                    st_name = st.get("name") if isinstance(st, dict) else st
                    if _check_ident(st_name, f"{stpath}.name" if isinstance(st, dict) else stpath, errors, "Nama state"):
                        if st_name in declared_states:
                            errors.append(ModelValidationError(stpath, f"Duplikat state '{st_name}'."))
                        declared_states.add(st_name)

            initial = sm.get("initial")
            if not isinstance(initial, str) or initial not in declared_states:
                errors.append(ModelValidationError(f"{smpath}.initial", f"Initial state '{initial}' tidak ditemukan di daftar states."))

            declared_events: Set[str] = set()
            if not isinstance(events_raw, list):
                errors.append(ModelValidationError(f"{smpath}.events", "Field 'events' harus berupa list."))
            else:
                for j, ev in enumerate(events_raw):
                    evpath = f"{smpath}.events[{j}]"
                    ev_name = ev.get("name") if isinstance(ev, dict) else ev
                    if _check_ident(ev_name, f"{evpath}.name" if isinstance(ev, dict) else evpath, errors, "Nama event"):
                        if ev_name in declared_events:
                            errors.append(ModelValidationError(evpath, f"Duplikat event '{ev_name}'."))
                        declared_events.add(ev_name)
                    if isinstance(ev, dict):
                        for k, p in enumerate(ev.get("params", [])):
                            ppath = f"{evpath}.params[{k}]"
                            if isinstance(p, dict):
                                _check_ident(p.get("name"), f"{ppath}.name", errors, "Nama parameter event")
                                _validate_typeref(p.get("type"), f"{ppath}.type", allow_void=False)

            if not isinstance(trans_raw, list):
                errors.append(ModelValidationError(f"{smpath}.transitions", "Field 'transitions' harus berupa list."))
            else:
                for j, tr in enumerate(trans_raw):
                    trpath = f"{smpath}.transitions[{j}]"
                    if not isinstance(tr, dict):
                        errors.append(ModelValidationError(trpath, "Transisi harus berupa objek."))
                        continue
                    src = tr.get("source") or tr.get("from")
                    dst = tr.get("target") or tr.get("to")
                    evn = tr.get("event")
                    if src not in declared_states:
                        errors.append(ModelValidationError(f"{trpath}.source", f"Source state '{src}' tidak dikenal."))
                    if dst not in declared_states:
                        errors.append(ModelValidationError(f"{trpath}.target", f"Target state '{dst}' tidak dikenal."))
                    if evn not in declared_events:
                        errors.append(ModelValidationError(f"{trpath}.event", f"Event '{evn}' tidak dikenal di state machine ini."))

    # 5. Validasi relationships
    rels_raw = data.get("relationships", [])
    if not isinstance(rels_raw, list):
        errors.append(ModelValidationError("relationships", "Field 'relationships' harus berupa list."))
        rels_raw = []

    seen_rels: Set[str] = set()
    for i, r in enumerate(rels_raw):
        rpath = f"relationships[{i}]"
        if not isinstance(r, dict):
            errors.append(ModelValidationError(rpath, "Relasi harus berupa objek."))
            continue
        rid = r.get("rel_id") or r.get("id")
        if _check_ident(rid, f"{rpath}.rel_id", errors, "ID relasi"):
            if rid in seen_rels:
                errors.append(ModelValidationError(f"{rpath}.rel_id", f"Duplikat ID relasi '{rid}'."))
            seen_rels.add(rid)

        kind = r.get("kind")
        if kind not in ("binary", "associative", "generalization"):
            errors.append(ModelValidationError(f"{rpath}.kind", f"Jenis relasi '{kind}' harus 'binary', 'associative', atau 'generalization'."))
            continue

        if kind in ("binary", "associative"):
            ends = r.get("ends")
            if not isinstance(ends, list) or len(ends) != 2:
                errors.append(ModelValidationError(f"{rpath}.ends", f"Relasi '{kind}' wajib memiliki tepat 2 elemen pada 'ends'."))
            else:
                for j, end in enumerate(ends):
                    epath = f"{rpath}.ends[{j}]"
                    if not isinstance(end, dict):
                        errors.append(ModelValidationError(epath, "Ujung relasi harus berupa objek."))
                        continue
                    cname = end.get("class_name") or end.get("class")
                    if cname not in declared_classes:
                        errors.append(ModelValidationError(f"{epath}.class_name", f"Kelas '{cname}' tidak ditemukan."))
                    try:
                        Multiplicity.parse(end.get("multiplicity", ""))
                    except ValueError as ex:
                        errors.append(ModelValidationError(f"{epath}.multiplicity", str(ex)))

            if kind == "associative":
                ac = r.get("assoc_class")
                if not ac or ac not in declared_classes:
                    errors.append(ModelValidationError(f"{rpath}.assoc_class", f"Association class '{ac}' tidak ditemukan di 'classes'."))

        elif kind == "generalization":
            sup = r.get("supertype")
            subs = r.get("subtypes")
            if sup not in declared_classes:
                errors.append(ModelValidationError(f"{rpath}.supertype", f"Supertype '{sup}' tidak ditemukan di 'classes'."))
            if not isinstance(subs, list) or len(subs) == 0:
                errors.append(ModelValidationError(f"{rpath}.subtypes", "Generalization wajib memiliki minimal 1 subtype."))
            else:
                for j, s in enumerate(subs):
                    if s not in declared_classes:
                        errors.append(ModelValidationError(f"{rpath}.subtypes[{j}]", f"Subtype '{s}' tidak ditemukan di 'classes'."))
                    elif s == sup:
                        errors.append(ModelValidationError(f"{rpath}.subtypes[{j}]", "Subtype tidak boleh sama dengan supertype."))

    return errors