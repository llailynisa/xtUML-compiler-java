"""Class Diagram: kelas (atribut/operasi), multiplicity, generalisasi, association class, dan kotak «enumeration»."""
from __future__ import annotations

from typing import Dict, List, Tuple

from ..ir.model import Model, Operation, TypeRef, XtClass
from .layout import (CHAR_W, LINE_H, DrawList, Ellipse, Line, Point, Rect, Text, along, clip_to_rect,
                     layered_layout, perp, text_width)

HDR_FILL = "#DCE9FF"
ENUM_FILL = "#FFF1CC"
ASSOC_FILL = "#E6F7E6"
PAD = 10


def type_label(t: TypeRef) -> str:
    if t.kind == "inst_ref":
        return f"inst_ref<{t.target}>"
    if t.kind == "inst_ref_set":
        return f"inst_ref_set<{t.target}>"
    return t.target if t.kind == "enum" and t.target else t.kind


def op_label(op: Operation) -> str:
    params = ", ".join(f"{p.name}: {type_label(p.type)}" for p in op.params)
    ret = "" if op.return_type.kind == "void" else f": {type_label(op.return_type)}"
    return f"+ {op.name}({params}){ret}" + (" {abstract}" if op.is_abstract else "")


class _Box:
    def __init__(self, title: List[Tuple[str, bool]], sections: List[List[str]], fill: str):
        self.title = title            # [(teks, bold)]
        self.sections = sections      # kompartemen berisi baris teks
        self.fill = fill
        lines = [t for t, _ in self.title] + [l for s in sections for l in s]
        self.w = max(130.0, max((text_width(l) for l in lines), default=0) + 2 * PAD)
        self.hdr_h = len(title) * LINE_H + 10
        self.sec_h = [max(len(s), 1) * LINE_H + 8 for s in sections]
        self.h = self.hdr_h + sum(self.sec_h)
        self.x = self.y = 0.0

    @property
    def center(self) -> Point:
        return self.x + self.w / 2, self.y + self.h / 2

    def edge_point(self, toward: Point) -> Point:
        cx, cy = self.center
        return clip_to_rect(cx, cy, self.w, self.h, toward[0], toward[1])

    def draw(self, dl: DrawList) -> None:
        dl.add(Rect(self.x, self.y, self.w, self.h, "#FFFFFF", "#333333"))
        dl.add(Rect(self.x, self.y, self.w, self.hdr_h, self.fill, "#333333"))
        for i, (t, bold) in enumerate(self.title):
            dl.add(Text(self.x + self.w / 2, self.y + 5 + i * LINE_H, t, "n", bold=bold,
                        italic=t.startswith("{")))
        y = self.y + self.hdr_h
        for lines, h in zip(self.sections, self.sec_h):
            for i, l in enumerate(lines):
                dl.add(Text(self.x + PAD, y + 4 + i * LINE_H, l, "nw", italic="{abstract}" in l))
            y += h
            if y < self.y + self.h - 0.5:
                dl.add(Line([(self.x, y), (self.x + self.w, y)]))


def _class_box(model: Model, c: XtClass, fill: str) -> _Box:
    title = []
    if c.is_abstract:
        title.append(("{abstract}", False))
    title.append((f"{c.name} ({c.key_letters})", True))
    attrs = [f"+ {a.name}: {type_label(a.type)}" for a in c.attributes]
    ops = [op_label(o) for o in c.operations]
    sections = [attrs, ops]
    if c.state_machine is not None:
        sections.append([f"[state machine: {len(c.state_machine.states)} state]"])
    return _Box(title, sections, fill)


def build_class_diagram(model: Model) -> DrawList:
    assoc_names = {r.assoc_class for r in model.relationships if r.kind == "associative" and r.assoc_class}
    boxes: Dict[str, _Box] = {}
    for c in model.classes:
        boxes[c.name] = _class_box(model, c, ASSOC_FILL if c.name in assoc_names else HDR_FILL)

    # edge untuk layout: generalisasi dulu (supertype di atas), lalu binary, lalu association class
    edges: List[Tuple[str, str]] = []
    for r in model.relationships:
        if r.kind == "generalization" and r.supertype:
            edges += [(r.supertype, s) for s in r.subtypes]
    for r in model.relationships:
        if r.kind in ("binary", "associative"):
            edges.append((r.ends[0].class_name, r.ends[1].class_name))
            if r.assoc_class:
                edges += [(r.ends[0].class_name, r.assoc_class), (r.ends[1].class_name, r.assoc_class)]
    pos = layered_layout({n: (b.w, b.h) for n, b in boxes.items()}, edges, h_gap=90, v_gap=150)
    for n, (x, y) in pos.items():
        boxes[n].x, boxes[n].y = x, y

    dl = DrawList()

    deferred: List[tuple] = []

    def defer(*args, **kw) -> None:
        deferred.append((args, kw))

    # ---- relasi (digambar dahulu agar berada di bawah kotak) ----------------------
    for r in model.relationships:
        if r.kind == "generalization":
            sup = boxes.get(r.supertype or "")
            if sup is None:
                continue
            for s in r.subtypes:
                sub = boxes.get(s)
                if sub is None:
                    continue
                p_sub = sub.edge_point(sup.center)
                p_sup = sup.edge_point(sub.center)
                dl.arrow([p_sub, p_sup], head="hollow")
                mx, my = (p_sub[0] + p_sup[0]) / 2, (p_sub[1] + p_sup[1]) / 2
                defer(mx, my, r.rel_id, bold=True)
            continue
        a, b = boxes[r.ends[0].class_name], boxes[r.ends[1].class_name]
        if a is b:  # relasi refleksif: lengkung persegi di sisi kanan
            x, y = a.x + a.w, a.y + 20
            pts = [(x, y), (x + 40, y), (x + 40, y + 40), (x, y + 40)]
            dl.add(Line(pts))
            defer(x + 40, y + 20, r.rel_id, bold=True)
            continue
        pa, pb = a.edge_point(b.center), b.edge_point(a.center)
        dl.add(Line([pa, pb]))
        mid = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
        for end, p, q, sign in ((r.ends[0], pa, pb, 1), (r.ends[1], pb, pa, -1)):
            ax, ay = along(p, q, 16)
            ox, oy = _side(p, q, str(end.multiplicity), sign)
            defer(ax + ox, ay + oy, str(end.multiplicity), bold=True)
            if end.phrase:
                bx, by = along(p, q, min(70, max(34, _dist(p, q) * 0.3)))
                px, py = _side(p, q, end.phrase, sign)
                defer(bx + px, by + py, end.phrase, italic=True, color="#555555")
        if r.assoc_class and r.assoc_class in boxes:
            ac = boxes[r.assoc_class]
            acx = ac.x + ac.w / 2
            if ac.y > mid[1]:       # association class di bawah garis relasi
                route = [(acx, ac.y), (acx, mid[1]), mid]
            elif ac.y + ac.h < mid[1]:
                route = [(acx, ac.y + ac.h), (acx, mid[1]), mid]
            else:
                route = [ac.edge_point(mid), mid]
            dl.add(Line(route, dash=True))
            dl.add(Ellipse(mid[0] - 3, mid[1] - 3, 6, 6, "#333333", "#333333"))
        defer(mid[0], mid[1], r.rel_id, bold=True)

    # ---- kotak kelas -----------------------------------------------------------------
    for b in boxes.values():
        b.draw(dl)
    for args, kw in deferred:  # label digambar terakhir agar tidak tertutup kotak
        dl.label(*args, **kw)

    # ---- enumeration: baris di bawah diagram ---------------------------------------------
    if model.enums:
        top = max((b.y + b.h for b in boxes.values()), default=0) + 70
        x = 0.0
        for e in model.enums:
            eb = _Box([("«enumeration»", False), (e.name, True)], [list(e.values)], ENUM_FILL)
            eb.x, eb.y = x, top
            eb.draw(dl)
            x += eb.w + 50
    return dl.normalize()


def _dist(p: Point, q: Point) -> float:
    return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5


def _side(p: Point, q: Point, text: str, sign: int) -> Point:
    """Offset tegak lurus garis p->q sehingga teks berada di samping garis (tidak menimpanya)."""
    ux, uy = perp(p, q, 1.0)
    dist = 7 + abs(ux) * text_width(text) / 2 + abs(uy) * LINE_H / 2
    return ux * dist * sign, uy * dist * sign
