"""Ekspor DrawList ke PNG/JPG memakai Pillow."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from ..ir.model import Model
from .class_diagram import build_class_diagram
from .layout import (FONT_PX, DrawList, Ellipse, Line, Polygon, Rect, Text)
from .state_diagram import build_state_diagram

_FONT_CANDIDATES = {
    (False, False): ["DejaVuSansMono.ttf", "Consolas.ttf", "consola.ttf", "Menlo.ttc", "cour.ttf", "LiberationMono-Regular.ttf"],
    (True, False): ["DejaVuSansMono-Bold.ttf", "consolab.ttf", "Menlo.ttc", "courbd.ttf", "LiberationMono-Bold.ttf"],
    (False, True): ["DejaVuSansMono-Oblique.ttf", "consolai.ttf", "Menlo.ttc", "couri.ttf", "LiberationMono-Italic.ttf"],
    (True, True): ["DejaVuSansMono-BoldOblique.ttf", "consolaz.ttf", "Menlo.ttc", "courbi.ttf", "LiberationMono-BoldItalic.ttf"],
}
_FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/usr/share/fonts/truetype/liberation",
              "/Library/Fonts", "/System/Library/Fonts", "C:/Windows/Fonts", str(Path.home() / ".fonts")]
_cache: Dict[tuple, object] = {}


def _font(bold: bool, italic: bool, size: int):
    from PIL import ImageFont
    key = (bold, italic, size)
    if key in _cache:
        return _cache[key]
    font = None
    for name in _FONT_CANDIDATES[(bold, italic)]:
        for d in _FONT_DIRS:
            p = os.path.join(d, name)
            if os.path.exists(p):
                try:
                    font = ImageFont.truetype(p, size)
                    break
                except OSError:
                    pass
        if font:
            break
    if font is None:
        try:
            font = ImageFont.load_default(size)
        except TypeError:  # Pillow lama
            font = ImageFont.load_default()
    _cache[key] = font
    return font


def render_image(dl: DrawList, scale: float = 2.0):
    """DrawList -> PIL.Image (RGB). scale=2 menghasilkan gambar tajam."""
    from PIL import Image, ImageDraw
    W, H = max(int(dl.width * scale), 1), max(int(dl.height * scale), 1)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    s = scale

    def sc(pts):
        return [(x * s, y * s) for x, y in pts]

    for it in dl.items:
        if isinstance(it, Rect):
            box = [it.x * s, it.y * s, (it.x + it.w) * s, (it.y + it.h) * s]
            if it.rounded:
                d.rounded_rectangle(box, radius=it.rounded * s, fill=it.fill, outline=it.outline, width=max(int(s), 1))
            else:
                d.rectangle(box, fill=it.fill, outline=it.outline, width=max(int(s), 1))
        elif isinstance(it, Ellipse):
            d.ellipse([it.x * s, it.y * s, (it.x + it.w) * s, (it.y + it.h) * s], fill=it.fill, outline=it.outline)
        elif isinstance(it, Polygon):
            d.polygon(sc(it.points), fill=it.fill, outline=it.outline)
        elif isinstance(it, Line):
            pts = sc(it.points)
            if it.dash:
                _dashed(d, pts, it.color, max(int(s), 1), 6 * s)
            else:
                d.line(pts, fill=it.color, width=max(int(s), 1), joint="curve")
        elif isinstance(it, Text):
            f = _font(it.bold, it.italic, int(FONT_PX * s))
            anchor = {"nw": "la", "n": "ma", "center": "mm"}[it.anchor]
            d.text((it.x * s, it.y * s), it.text, fill=it.color, font=f, anchor=anchor)
    return img


def _dashed(d, pts, color, width, dash):
    import math
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        n = int(length // dash) or 1
        for i in range(0, n, 2):
            a, b = i / n, min((i + 1) / n, 1.0)
            d.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)], fill=color, width=width)


def save_image(dl: DrawList, path: Union[str, Path], fmt: Optional[str] = None, scale: float = 2.0) -> Path:
    """Menyimpan ke PNG atau JPG (format dari ekstensi bila fmt kosong)."""
    p = Path(path)
    f = (fmt or p.suffix.lstrip(".") or "png").lower()
    if f in ("jpg", "jpeg"):
        f = "JPEG"
    elif f == "png":
        f = "PNG"
    else:
        raise ValueError(f"format gambar tidak didukung: {f} (gunakan png atau jpg)")
    p.parent.mkdir(parents=True, exist_ok=True)
    render_image(dl, scale).save(p, f, **({"quality": 92} if f == "JPEG" else {}))
    return p


def save_all_diagrams(model: Model, out_dir: Union[str, Path], fmt: str = "png") -> List[Path]:
    """Menyimpan class_diagram.<fmt> dan state_<Class>.<fmt> untuk setiap class ber-state machine."""
    out = Path(out_dir)
    ext = "jpg" if fmt.lower() in ("jpg", "jpeg") else "png"
    written = [save_image(build_class_diagram(model), out / f"class_diagram.{ext}")]
    for c in model.classes:
        if c.state_machine is not None:
            written.append(save_image(build_state_diagram(c.state_machine, c.name), out / f"state_{c.name}.{ext}"))
    return written