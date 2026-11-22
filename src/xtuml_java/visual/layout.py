"""Primitif gambar netral-renderer + algoritma layout.

Diagram dibangun sebagai DrawList (Rect/Ellipse/Polygon/Line/Text). DrawList yang sama
dirender oleh Tkinter Canvas (pratinjau GUI) dan oleh Pillow (ekspor PNG/JPG).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

CHAR_W = 7.2   # lebar karakter font monospace 12px
LINE_H = 16
FONT_PX = 12

Point = Tuple[float, float]


def text_width(s: str) -> float:
    return len(s) * CHAR_W


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float
    fill: str = "#FFFFFF"
    outline: str = "#333333"
    dash: bool = False
    rounded: float = 0


@dataclass
class Ellipse:
    x: float
    y: float
    w: float
    h: float
    fill: str = "#FFFFFF"
    outline: str = "#333333"


@dataclass
class Polygon:
    points: List[Point]
    fill: str = "#FFFFFF"
    outline: str = "#333333"


@dataclass
class Line:
    points: List[Point]
    color: str = "#333333"
    dash: bool = False


@dataclass
class Text:
    x: float
    y: float
    text: str
    anchor: str = "nw"      # nw | n | center
    bold: bool = False
    italic: bool = False
    color: str = "#111111"


Item = object


@dataclass
class DrawList:
    items: List[Item] = field(default_factory=list)
    width: float = 0
    height: float = 0

    def add(self, item: Item) -> Item:
        self.items.append(item)
        return item

    # ---- helper komposit -------------------------------------------------
    def arrow(self, points: Sequence[Point], head: Optional[str] = "open", tail: Optional[str] = None,
              color: str = "#333333", dash: bool = False) -> None:
        pts = list(points)
        self.add(Line(pts, color, dash))
        if head:
            self.add(_head(pts[-2], pts[-1], head, color))
        if tail:
            self.add(_head(pts[1], pts[0], tail, color))

    def label(self, x: float, y: float, text: str, bg: bool = True, **kw) -> None:
        if bg and text:
            w = text_width(text) + 4
            self.add(Rect(x - w / 2, y - LINE_H / 2, w, LINE_H, "#FFFFFF", "#FFFFFF"))
        self.add(Text(x, y, text, "center", **kw))

    # ---- bounds ------------------------------------------------------------
    def _extent(self) -> Tuple[float, float, float, float]:
        xs: List[float] = []
        ys: List[float] = []
        for it in self.items:
            if isinstance(it, (Rect, Ellipse)):
                xs += [it.x, it.x + it.w]
                ys += [it.y, it.y + it.h]
            elif isinstance(it, (Polygon, Line)):
                xs += [p[0] for p in it.points]
                ys += [p[1] for p in it.points]
            elif isinstance(it, Text):
                w = text_width(it.text)
                if it.anchor == "nw":
                    xs += [it.x, it.x + w]
                    ys += [it.y, it.y + LINE_H]
                elif it.anchor == "n":
                    xs += [it.x - w / 2, it.x + w / 2]
                    ys += [it.y, it.y + LINE_H]
                else:
                    xs += [it.x - w / 2, it.x + w / 2]
                    ys += [it.y - LINE_H / 2, it.y + LINE_H / 2]
        if not xs:
            return 0, 0, 0, 0
        return min(xs), min(ys), max(xs), max(ys)

    def normalize(self, margin: float = 24) -> "DrawList":
        """Geser semua item agar pojok kiri-atas = (margin, margin); hitung width/height."""
        x0, y0, x1, y1 = self._extent()
        dx, dy = margin - x0, margin - y0
        for it in self.items:
            if isinstance(it, (Rect, Ellipse, Text)):
                it.x += dx
                it.y += dy
            elif isinstance(it, (Polygon, Line)):
                it.points = [(px + dx, py + dy) for px, py in it.points]
        self.width = (x1 - x0) + 2 * margin
        self.height = (y1 - y0) + 2 * margin
        return self


def _head(frm: Point, to: Point, kind: str, color: str) -> Polygon:
    """Kepala panah di titik `to` yang datang dari `frm`."""
    ang = math.atan2(to[1] - frm[1], to[0] - frm[0])
    size, spread = (14, 0.45) if kind == "hollow" else (11, 0.42)
    p1 = (to[0] - size * math.cos(ang - spread), to[1] - size * math.sin(ang - spread))
    p2 = (to[0] - size * math.cos(ang + spread), to[1] - size * math.sin(ang + spread))
    fill = {"hollow": "#FFFFFF", "filled": color, "open": color}[kind]
    return Polygon([to, p1, p2], fill, color)


# ---------------------------------------------------------------------------
# Geometri
# ---------------------------------------------------------------------------

def clip_to_rect(cx: float, cy: float, w: float, h: float, tx: float, ty: float) -> Point:
    """Titik tempat garis dari pusat (cx,cy) ke (tx,ty) keluar dari persegi panjang w x h."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = (w / 2) / abs(dx) if dx else float("inf")
    sy = (h / 2) / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def along(p: Point, q: Point, dist: float) -> Point:
    d = math.hypot(q[0] - p[0], q[1] - p[1]) or 1.0
    return p[0] + (q[0] - p[0]) * dist / d, p[1] + (q[1] - p[1]) * dist / d


def perp(p: Point, q: Point, dist: float) -> Point:
    """Vektor tegak lurus (kiri arah p->q) sepanjang dist."""
    d = math.hypot(q[0] - p[0], q[1] - p[1]) or 1.0
    return -(q[1] - p[1]) * dist / d, (q[0] - p[0]) * dist / d


# ---------------------------------------------------------------------------
# Layout berlapis (layered) untuk class diagram
# ---------------------------------------------------------------------------

def layered_layout(sizes: Dict[str, Tuple[float, float]], edges: List[Tuple[str, str]],
                   h_gap: float = 70, v_gap: float = 100) -> Dict[str, Point]:
    """Posisi kiri-atas tiap node. Edge (a, b) berarti a sebaiknya berada di atas b."""
    names = list(sizes)
    out: Dict[str, List[str]] = {n: [] for n in names}

    def reachable(src: str, dst: str) -> bool:
        stack, seen = [src], set()
        while stack:
            n = stack.pop()
            if n == dst:
                return True
            if n in seen:
                continue
            seen.add(n)
            stack.extend(out[n])
        return False

    for a, b in edges:  # buang edge yang membentuk siklus
        if a != b and a in out and b in out and b not in out[a] and not reachable(b, a):
            out[a].append(b)

    layer: Dict[str, int] = {n: 0 for n in names}
    for _ in range(len(names) + 1):
        changed = False
        for a in names:
            for b in out[a]:
                if layer[b] < layer[a] + 1:
                    layer[b] = layer[a] + 1
                    changed = True
        if not changed:
            break

    rows: Dict[int, List[str]] = {}
    for n in names:
        rows.setdefault(layer[n], []).append(n)
    nbrs: Dict[str, List[str]] = {n: [] for n in names}
    for a, b in edges:
        if a in nbrs and b in nbrs and a != b:
            nbrs[a].append(b)
            nbrs[b].append(a)

    def order_index() -> Dict[str, float]:
        return {n: i for r in rows.values() for i, n in enumerate(r)}

    for _ in range(4):  # barycenter sweep
        idx = order_index()
        for lv in sorted(rows):
            def key(n: str) -> float:
                ns = [idx[m] for m in nbrs[n] if layer[m] != lv]
                return sum(ns) / len(ns) if ns else idx[n]
            rows[lv].sort(key=key)
            idx = order_index()

    widths = {lv: sum(sizes[n][0] for n in r) + h_gap * (len(r) - 1) for lv, r in rows.items()}
    maxw = max(widths.values()) if widths else 0
    pos: Dict[str, Point] = {}
    y = 0.0
    for lv in sorted(rows):
        x = (maxw - widths[lv]) / 2
        for n in rows[lv]:
            pos[n] = (x, y)
            x += sizes[n][0] + h_gap
        y += max(sizes[n][1] for n in rows[lv]) + v_gap
    return pos