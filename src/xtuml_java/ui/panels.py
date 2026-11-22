"""Panel-panel Tkinter modern (Clean Light theme): editor JSON, kanvas diagram, pratinjau Java, dan panel error."""
from __future__ import annotations

import json
import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from typing import Dict, List, Optional

from ..loader.validator import ModelValidationError
from ..visual.layout import FONT_PX, DrawList, Ellipse, Line, Polygon, Rect, Text

# Palet warna Clean Light Modern (Slate & Indigo)
PALETTE = {
    "bg_app": "#F8FAFC",
    "bg_card": "#FFFFFF",
    "bg_subtle": "#F1F5F9",
    "border": "#E2E8F0",
    "text_primary": "#0F172A",
    "text_secondary": "#475569",
    "text_muted": "#94A3B8",
    "accent": "#2563EB",
    "accent_hover": "#1D4ED8",
    "accent_soft": "#EFF6FF",
    "success": "#15803D",
    "success_soft": "#F0FDF4",
    "danger": "#B91C1C",
    "danger_soft": "#FEF2F2",
    "warning": "#B45309",
    "warning_soft": "#FFFBEB",
}

_MONO_PREFERENCE = ("JetBrains Mono", "Cascadia Code", "DejaVu Sans Mono", "Consolas", "Menlo", "Courier New")
_UI_PREFERENCE = ("Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Arial")


def get_mono_family(root: tk.Misc) -> str:
    available = set(tkfont.families(root))
    for f in _MONO_PREFERENCE:
        if f in available:
            return f
    return "Courier"


def get_ui_family(root: tk.Misc) -> str:
    available = set(tkfont.families(root))
    for f in _UI_PREFERENCE:
        if f in available:
            return f
    return "TkDefaultFont"


def _rounded_points(x0: float, y0: float, x1: float, y1: float, r: float) -> List[float]:
    return [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
        x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]


def draw_on_canvas(canvas: tk.Canvas, dl: DrawList, zoom: float = 1.0, family: str = "Courier") -> None:
    """Merender DrawList ke Tk Canvas (DrawList yang sama dipakai ekspor Pillow)."""
    canvas.delete("all")
    fonts: Dict[tuple, tkfont.Font] = {}

    def font(bold: bool, italic: bool) -> tkfont.Font:
        key = (bold, italic)
        if key not in fonts:
            fonts[key] = tkfont.Font(
                family=family,
                size=-max(int(FONT_PX * zoom), 6),
                weight="bold" if bold else "normal",
                slant="italic" if italic else "roman",
            )
        return fonts[key]

    z = zoom
    for it in dl.items:
        if isinstance(it, Rect):
            if it.rounded:
                canvas.create_polygon(
                    _rounded_points(it.x * z, it.y * z, (it.x + it.w) * z, (it.y + it.h) * z, it.rounded * z),
                    smooth=True,
                    fill=it.fill,
                    outline=it.outline,
                )
            else:
                canvas.create_rectangle(
                    it.x * z, it.y * z, (it.x + it.w) * z, (it.y + it.h) * z,
                    fill=it.fill,
                    outline=it.outline,
                )
        elif isinstance(it, Ellipse):
            canvas.create_oval(
                it.x * z, it.y * z, (it.x + it.w) * z, (it.y + it.h) * z,
                fill=it.fill,
                outline=it.outline,
            )
        elif isinstance(it, Polygon):
            canvas.create_polygon([c * z for p in it.points for c in p], fill=it.fill, outline=it.outline)
        elif isinstance(it, Line):
            canvas.create_line(
                [c * z for p in it.points for c in p],
                fill=it.color,
                dash=(6, 4) if it.dash else None,
            )
        elif isinstance(it, Text):
            anchor = {"nw": tk.NW, "n": tk.N, "center": tk.CENTER}[it.anchor]
            canvas.create_text(
                it.x * z, it.y * z,
                text=it.text,
                anchor=anchor,
                fill=it.color,
                font=font(it.bold, it.italic),
            )
    canvas.configure(scrollregion=(0, 0, max(dl.width * z, 100), max(dl.height * z, 100)))


class _CodeTextArea(tk.Frame):
    """Widget editor/viewer kode dengan gutter nomor baris dan syntax highlighting ringan."""

    def __init__(self, master: tk.Misc, readonly: bool = False, mode: str = "json"):
        super().__init__(master, bg=PALETTE["bg_card"], highlightthickness=1, highlightbackground=PALETTE["border"])
        self.readonly = readonly
        self.mode = mode
        mono = get_mono_family(self)

        self.gutter = tk.Text(
            self,
            width=4,
            padx=8,
            pady=10,
            takefocus=0,
            borderwidth=0,
            highlightthickness=0,
            bg=PALETTE["bg_subtle"],
            fg=PALETTE["text_muted"],
            font=(mono, 10),
            state="disabled",
            wrap="none",
        )
        self.text = tk.Text(
            self,
            wrap="none",
            undo=not readonly,
            padx=12,
            pady=10,
            borderwidth=0,
            highlightthickness=0,
            bg=PALETTE["bg_card"],
            fg=PALETTE["text_primary"],
            insertbackground=PALETTE["accent"],
            selectbackground="#DBEAFE",
            selectforeground=PALETTE["text_primary"],
            font=(mono, 10),
        )
        if readonly:
            self.text.configure(state="disabled")

        ys = ttk.Scrollbar(self, orient="vertical", command=self._on_yscroll)
        xs = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=lambda *args: self._sync_scroll(ys, *args), xscrollcommand=xs.set)

        self.gutter.grid(row=0, column=0, sticky="ns")
        self.text.grid(row=0, column=1, sticky="nsew")
        ys.grid(row=0, column=2, sticky="ns")
        xs.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        self._setup_tags()
        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<KeyRelease>", lambda _e: self._refresh_extras())

    def _setup_tags(self) -> None:
        self.text.tag_configure("key", foreground="#1D4ED8")
        self.text.tag_configure("str", foreground="#047857")
        self.text.tag_configure("num", foreground="#B45309")
        self.text.tag_configure("kw", foreground="#7C3AED")
        self.text.tag_configure("comment", foreground="#64748B")
        self.text.tag_configure("todo", foreground="#B45309", background="#FEF3C7")

    def _on_yscroll(self, *args) -> None:
        self.text.yview(*args)
        self.gutter.yview(*args)

    def _sync_scroll(self, scrollbar: ttk.Scrollbar, first: str, last: str) -> None:
        scrollbar.set(first, last)
        self.gutter.yview_moveto(first)

    def _on_modified(self, _event=None) -> None:
        if self.text.edit_modified():
            self._refresh_extras()
            self.text.edit_modified(False)

    def _refresh_extras(self) -> None:
        content = self.text.get("1.0", "end-1c")
        line_count = content.count("\n") + 1
        nums = "\n".join(str(i) for i in range(1, line_count + 1))

        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        self.gutter.insert("1.0", nums)
        self.gutter.configure(state="disabled")
        self.gutter.yview_moveto(self.text.yview()[0])

        for tag in ("key", "str", "num", "kw", "comment", "todo"):
            self.text.tag_remove(tag, "1.0", "end")

        if self.mode == "json":
            self._highlight_pattern(r'"[^"\\]*(?:\\.[^"\\]*)*"\s*(?=:)', "key")
            self._highlight_pattern(r'(?<=:)\s*"[^"\\]*(?:\\.[^"\\]*)*"', "str")
            self._highlight_pattern(r'\b(true|false|null)\b', "kw")
            self._highlight_pattern(r'\b-?\d+(?:\.\d+)?\b', "num")
        elif self.mode == "java":
            self._highlight_pattern(
                r'\b(package|import|public|private|protected|abstract|class|enum|extends|implements|'
                r'void|int|boolean|double|long|new|return|if|else|switch|case|break|for|try|catch|final|static|this|super)\b',
                "kw",
            )
            self._highlight_pattern(r'"[^"\\]*(?:\\.[^"\\]*)*"', "str")
            self._highlight_pattern(r'//.*', "comment")
            self._highlight_pattern(r'//\s*TODO.*', "todo")

    def _highlight_pattern(self, pattern: str, tag: str) -> None:
        content = self.text.get("1.0", "end-1c")
        for m in re.finditer(pattern, content):
            start = f"1.0 + {m.start()} chars"
            end = f"1.0 + {m.end()} chars"
            self.text.tag_add(tag, start, end)

    def get_value(self) -> str:
        return self.text.get("1.0", "end-1c")

    def set_value(self, s: str) -> None:
        if self.readonly:
            self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", s)
        self._refresh_extras()
        if self.readonly:
            self.text.configure(state="disabled")


class JsonEditorPanel(tk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, bg=PALETTE["bg_card"], highlightthickness=1, highlightbackground=PALETTE["border"])
        ui_font = get_ui_family(self)

        header = tk.Frame(self, bg=PALETTE["bg_card"], padx=12, pady=8)
        header.pack(fill="x")
        tk.Label(
            header,
            text="Model xtUML (JSON)",
            bg=PALETTE["bg_card"],
            fg=PALETTE["text_primary"],
            font=(ui_font, 10, "bold"),
        ).pack(side="left")

        ttk.Button(header, text="Rapikan JSON", style="Subtle.TButton", command=self.format_json).pack(side="right")

        tk.Frame(self, height=1, bg=PALETTE["border"]).pack(fill="x")

        self.editor = _CodeTextArea(self, readonly=False, mode="json")
        self.editor.configure(highlightthickness=0)
        self.editor.pack(fill="both", expand=True)
        self.text = self.editor.text  # kompatibilitas jika ada referensi langsung ke .text

    def format_json(self) -> None:
        raw = self.get_text().strip()
        if not raw:
            return
        try:
            parsed = json.loads(raw)
            self.set_text(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            pass  # Biarkan error JSON tetap ditangani panel error saat compile

    def get_text(self) -> str:
        return self.editor.get_value()

    def set_text(self, s: str) -> None:
        self.editor.set_value(s)


class DiagramCanvasPanel(tk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, bg=PALETTE["bg_card"])
        ui_font = get_ui_family(self)

        bar = tk.Frame(self, bg=PALETTE["bg_subtle"], padx=10, pady=6)
        bar.pack(fill="x")

        self.zoom_label = tk.StringVar(value="100%")
        ttk.Button(bar, text="−", width=3, style="Subtle.TButton", command=lambda: self.set_zoom(self.zoom / 1.15)).pack(side="left", padx=2)
        tk.Label(
            bar,
            textvariable=self.zoom_label,
            width=6,
            bg=PALETTE["bg_subtle"],
            fg=PALETTE["text_secondary"],
            font=(ui_font, 9, "bold"),
        ).pack(side="left", padx=2)
        ttk.Button(bar, text="+", width=3, style="Subtle.TButton", command=lambda: self.set_zoom(self.zoom * 1.15)).pack(side="left", padx=2)
        ttk.Button(bar, text="Reset 100%", style="Subtle.TButton", command=lambda: self.set_zoom(1.0)).pack(side="left", padx=(6, 2))

        tk.Label(
            bar,
            text="Tips: Klik & geser untuk pan • Ctrl + Scroll untuk zoom",
            bg=PALETTE["bg_subtle"],
            fg=PALETTE["text_muted"],
            font=(ui_font, 8),
        ).pack(side="right", padx=4)

        tk.Frame(self, height=1, bg=PALETTE["border"]).pack(fill="x")

        wrap = tk.Frame(self, bg="#FFFFFF")
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, background="#FFFFFF", highlightthickness=0, cursor="hand2")
        ys = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        xs = ttk.Scrollbar(wrap, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        # Interaksi drag-to-pan dan Ctrl+MouseWheel zoom
        self.canvas.bind("<ButtonPress-1>", self._start_pan)
        self.canvas.bind("<B1-Motion>", self._do_pan)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_wheel)

        self.zoom = 1.0
        self.current: Optional[DrawList] = None
        self._family = get_mono_family(self)

    def _start_pan(self, event: tk.Event) -> None:
        self.canvas.scan_mark(event.x, event.y)

    def _do_pan(self, event: tk.Event) -> None:
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_ctrl_wheel(self, event: tk.Event) -> None:
        factor = 1.1 if event.delta > 0 else (1 / 1.1)
        self.set_zoom(self.zoom * factor)

    def show(self, dl: Optional[DrawList]) -> None:
        self.current = dl
        if dl is None:
            self.canvas.delete("all")
            return
        draw_on_canvas(self.canvas, dl, self.zoom, self._family)

    def set_zoom(self, z: float) -> None:
        self.zoom = max(0.3, min(z, 3.0))
        self.zoom_label.set(f"{int(round(self.zoom * 100))}%")
        if self.current is not None:
            draw_on_canvas(self.canvas, self.current, self.zoom, self._family)


class StateDiagramPanel(tk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, bg=PALETTE["bg_card"])
        ui_font = get_ui_family(self)

        top = tk.Frame(self, bg=PALETTE["bg_card"], padx=12, pady=8)
        top.pack(fill="x")
        tk.Label(
            top,
            text="Pilih Class State Machine:",
            bg=PALETTE["bg_card"],
            fg=PALETTE["text_secondary"],
            font=(ui_font, 9, "bold"),
        ).pack(side="left", padx=(0, 8))

        self.choice = tk.StringVar()
        self.combo = ttk.Combobox(top, textvariable=self.choice, state="readonly", width=32)
        self.combo.pack(side="left")
        self.combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh())

        tk.Frame(self, height=1, bg=PALETTE["border"]).pack(fill="x")

        self.canvas_panel = DiagramCanvasPanel(self)
        self.canvas_panel.pack(fill="both", expand=True)
        self.diagrams: Dict[str, DrawList] = {}

    def set_diagrams(self, diagrams: Dict[str, DrawList]) -> None:
        self.diagrams = diagrams
        names = list(diagrams)
        self.combo["values"] = names
        self.choice.set(names[0] if names else "")
        self._refresh()

    def _refresh(self) -> None:
        self.canvas_panel.show(self.diagrams.get(self.choice.get()))

    @property
    def current(self) -> Optional[DrawList]:
        return self.canvas_panel.current

    @property
    def current_name(self) -> str:
        return self.choice.get()


class JavaPreviewPanel(tk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, bg=PALETTE["bg_card"])
        ui_font = get_ui_family(self)

        top = tk.Frame(self, bg=PALETTE["bg_card"], padx=12, pady=8)
        top.pack(fill="x")
        tk.Label(
            top,
            text="Berkas Java Hasil Kompilasi:",
            bg=PALETTE["bg_card"],
            fg=PALETTE["text_secondary"],
            font=(ui_font, 9, "bold"),
        ).pack(side="left", padx=(0, 8))

        self.choice = tk.StringVar()
        self.combo = ttk.Combobox(top, textvariable=self.choice, state="readonly", width=38)
        self.combo.pack(side="left")
        self.combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh())

        self.copy_btn_text = tk.StringVar(value="Salin Kode")
        ttk.Button(top, textvariable=self.copy_btn_text, style="Subtle.TButton", command=self._copy_code).pack(side="right")

        tk.Frame(self, height=1, bg=PALETTE["border"]).pack(fill="x")

        self.viewer = _CodeTextArea(self, readonly=True, mode="java")
        self.viewer.configure(highlightthickness=0)
        self.viewer.pack(fill="both", expand=True)
        self.text = self.viewer.text
        self.files: Dict[str, str] = {}

    def _copy_code(self) -> None:
        code = self.files.get(self.choice.get(), "")
        if not code:
            return
        self.clipboard_clear()
        self.clipboard_append(code)
        self.copy_btn_text.set("Tersalin ✓")
        self.after(1500, lambda: self.copy_btn_text.set("Salin Kode"))

    def set_files(self, files: Dict[str, str], preferred: str = "") -> None:
        self.files = files
        names = list(files)
        self.combo["values"] = names
        self.choice.set(preferred if preferred in files else (names[0] if names else ""))
        self._refresh()

    def _refresh(self) -> None:
        self.viewer.set_value(self.files.get(self.choice.get(), ""))


class ErrorPanel(tk.Frame):
    """Menampilkan ModelValidationError ber-path dan daftar TODO secara bersih."""

    def __init__(self, master: tk.Misc):
        super().__init__(master, bg=PALETTE["bg_card"])
        ui_font = get_ui_family(self)

        banner = tk.Frame(self, bg=PALETTE["bg_subtle"], padx=12, pady=10)
        banner.pack(fill="x")
        self.summary = tk.StringVar(value="Belum ada proses compile yang dijalankan.")
        tk.Label(
            banner,
            textvariable=self.summary,
            bg=PALETTE["bg_subtle"],
            fg=PALETTE["text_primary"],
            font=(ui_font, 9, "bold"),
        ).pack(anchor="w")

        tk.Frame(self, height=1, bg=PALETTE["border"]).pack(fill="x")

        wrap = tk.Frame(self, bg=PALETTE["bg_card"])
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=("sev", "path", "msg"), show="headings")
        for col, title, width in (("sev", "Status", 95), ("path", "Lokasi Path", 260), ("msg", "Keterangan", 520)):
            self.tree.heading(col, text=title, anchor="w")
            self.tree.column(col, width=width, anchor="w")

        self.tree.tag_configure("error", foreground=PALETTE["danger"], background=PALETTE["danger_soft"])
        self.tree.tag_configure("warning", foreground=PALETTE["warning"], background=PALETTE["warning_soft"])
        self.tree.tag_configure("todo", foreground=PALETTE["text_secondary"], background=PALETTE["bg_subtle"])

        ys = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def show_errors(
        self,
        errors: List[ModelValidationError],
        todos: Optional[List[str]] = None,
        ok_message: str = "",
    ) -> None:
        self.clear()
        n_err = sum(1 for e in errors if e.severity == "error")
        n_warn = len(errors) - n_err
        for e in errors:
            self.tree.insert(
                "",
                "end",
                values=("ERROR" if e.severity == "error" else "PERINGATAN", e.path, e.message),
                tags=(e.severity,),
            )
        for t in todos or []:
            self.tree.insert("", "end", values=("TODO", "oal", t), tags=("todo",))
        if n_err:
            self.summary.set(f"Compile gagal: {n_err} error, {n_warn} peringatan. Perbaiki JSON lalu compile ulang.")
        else:
            extra = f" • {len(todos)} baris OAL menjadi // TODO." if todos else ""
            self.summary.set((ok_message or "Compile berhasil.") + (f" ({n_warn} peringatan)" if n_warn else "") + extra)