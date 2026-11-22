"""Visualisasi State Diagram xtUML menjadi DrawList (netral-renderer untuk Tk & Pillow)."""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from ..ir.model import State, StateMachine, Transition
from .layout import (
    LINE_H,
    DrawList,
    Ellipse,
    Line,
    Point,
    Rect,
    Text,
    clip_to_rect,
    layered_layout,
    perp,
    text_width,
)

PAD_X = 14.0
PAD_Y = 10.0
MIN_STATE_W = 140.0
MAX_ACTION_CHARS = 38


def _truncate(s: str, limit: int = MAX_ACTION_CHARS) -> str:
    return s if len(s) <= limit else s[: limit - 3] + "..."


def _state_box_size(st: State) -> Tuple[float, float]:
    title = st.name
    action_lines = [f"entry / {_truncate(line.strip())}" for line in st.action if line.strip()]
    widths = [text_width(title)] + [text_width(al) for al in action_lines]
    w = max(MIN_STATE_W, max(widths) + 2 * PAD_X)

    if action_lines:
        h = PAD_Y + LINE_H + 8 + len(action_lines) * LINE_H + PAD_Y
    else:
        h = PAD_Y + LINE_H + PAD_Y
    return w, h


def _draw_state_box(dl: DrawList, x: float, y: float, w: float, h: float, st: State, is_initial: bool) -> None:
    outline = "#1B5E20" if is_initial else "#2C3E50"
    fill = "#F4FBF6" if is_initial else "#FFFFFF"
    dl.add(Rect(x, y, w, h, fill=fill, outline=outline, rounded=12))

    # Nama State (centered di bagian atas)
    dl.add(Text(x + w / 2, y + PAD_Y, st.name, anchor="n", bold=True, color="#111111"))

    action_lines = [f"entry / {_truncate(line.strip())}" for line in st.action if line.strip()]
    if action_lines:
        sep_y = y + PAD_Y + LINE_H + 4
        dl.add(Line([(x, sep_y), (x + w, sep_y)], color=outline))
        ay = sep_y + 6
        for al in action_lines:
            dl.add(Text(x + PAD_X, ay, al, anchor="nw", italic=True, color="#333333"))
            ay += LINE_H


def build_state_diagram(sm: Optional[StateMachine], class_name: str = "") -> DrawList:
    """Membangun DrawList State Diagram untuk satu StateMachine."""
    dl = DrawList()
    if sm is None or not sm.states:
        title = f"State Machine: {class_name} (kosong)" if class_name else "State Machine (kosong)"
        dl.add(Text(0, 0, title, anchor="nw", italic=True, color="#666666"))
        return dl.normalize()

    sizes: Dict[str, Tuple[float, float]] = {st.name: _state_box_size(st) for st in sm.states}
    edges: List[Tuple[str, str]] = [(tr.source, tr.target) for tr in sm.transitions if tr.source != tr.target]

    # Hitung tata letak kotak state
    positions = layered_layout(sizes, edges, h_gap=95, v_gap=95)

    # Pastikan initial state berada di baris paling atas jika tergeser karena siklus
    if sm.initial in positions:
        min_y = min(p[1] for p in positions.values())
        ix, iy = positions[sm.initial]
        if iy > min_y:
            positions[sm.initial] = (ix, min_y - 110)

    # Gambar kotak setiap State
    for st in sm.states:
        x, y = positions[st.name]
        w, h = sizes[st.name]
        _draw_state_box(dl, x, y, w, h, st, is_initial=(st.name == sm.initial))

    # Gambar Initial Pseudo-State (lingkaran hitam solid + panah ke initial state)
    if sm.initial in positions:
        ix, iy = positions[sm.initial]
        iw, _ = sizes[sm.initial]
        r = 9.0
        cx = ix + iw / 2
        cy = iy - 46.0
        dl.add(Ellipse(cx - r, cy - r, 2 * r, 2 * r, fill="#111111", outline="#111111"))
        dl.arrow([(cx, cy + r), (cx, iy)], head="open", color="#111111")

    # Kelompokkan transisi antar-pasangan (src, dst) agar paralel/bolak-balik tidak bertumpuk
    pair_counts: Dict[Tuple[str, str], int] = {}
    for tr in sm.transitions:
        pair_counts[(tr.source, tr.target)] = pair_counts.get((tr.source, tr.target), 0) + 1

    pair_seen: Dict[Tuple[str, str], int] = {}
    for tr in sm.transitions:
        if tr.source not in positions or tr.target not in positions:
            continue
        sx, sy = positions[tr.source]
        sw, sh = sizes[tr.source]
        scx, scy = sx + sw / 2, sy + sh / 2

        idx = pair_seen.get((tr.source, tr.target), 0)
        pair_seen[(tr.source, tr.target)] = idx + 1

        # Kasus 1: Self-transition (loop di sisi kanan state)
        if tr.source == tr.target:
            loop_w = 36.0 + idx * 18.0
            loop_h = min(sh * 0.55, 28.0)
            y_top = scy - loop_h / 2
            y_bot = scy + loop_h / 2
            p0: Point = (sx + sw, y_top)
            p1: Point = (sx + sw + loop_w, y_top)
            p2: Point = (sx + sw + loop_w, y_bot)
            p3: Point = (sx + sw, y_bot)
            dl.arrow([p0, p1, p2, p3], head="open", color="#2C3E50")
            lbl_x = sx + sw + loop_w + 8 + text_width(tr.event) / 2
            dl.label(lbl_x, scy, tr.event, bg=True, color="#1A237E")
            continue

        # Kasus 2: Transisi antar dua state berbeda
        tx, ty = positions[tr.target]
        tw, th = sizes[tr.target]
        tcx, tcy = tx + tw / 2, ty + th / 2

        has_reverse = (tr.target, tr.source) in pair_counts
        total_same_dir = pair_counts[(tr.source, tr.target)]

        # Hitung offset tegak lurus jika ada arah sebaliknya atau transisi paralel
        offset = 0.0
        if has_reverse:
            offset += 18.0
        if total_same_dir > 1:
            offset += (idx - (total_same_dir - 1) / 2.0) * 24.0

        p_start = clip_to_rect(scx, scy, sw, sh, tcx, tcy)
        p_end = clip_to_rect(tcx, tcy, tw, th, scx, scy)

        if abs(offset) > 0.1:
            ox, oy = perp((scx, scy), (tcx, tcy), offset)
            mid_x = (p_start[0] + p_end[0]) / 2 + ox
            mid_y = (p_start[1] + p_end[1]) / 2 + oy
            p_start = clip_to_rect(scx, scy, sw, sh, mid_x, mid_y)
            p_end = clip_to_rect(tcx, tcy, tw, th, mid_x, mid_y)
            dl.arrow([p_start, (mid_x, mid_y), p_end], head="open", color="#2C3E50")
            dl.label(mid_x, mid_y, tr.event, bg=True, color="#1A237E")
        else:
            dl.arrow([p_start, p_end], head="open", color="#2C3E50")
            mid_x = (p_start[0] + p_end[0]) / 2
            mid_y = (p_start[1] + p_end[1]) / 2
            dl.label(mid_x, mid_y, tr.event, bg=True, color="#1A237E")

    # Judul diagram di pojok kiri atas (sebelum normalize)
    if class_name:
        x0, y0, _, _ = dl._extent()
        dl.add(Text(x0, y0 - 28, f"State Machine: {class_name}", anchor="nw", bold=True, color="#111111"))

    return dl.normalize(margin=24)