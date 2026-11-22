"""Aplikasi desktop Tkinter (Clean Light Modern): editor JSON -> compile -> pratinjau -> Simpan/Export."""
from __future__ import annotations
from ..generator.emitter import RUNTIME_FILES, GeneratedProject, generate_project, write_project
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from ..generator.emitter import GeneratedProject, generate_project, write_project
from ..ir.model import Model
from ..loader.json_loader import load_from_text
from ..loader.validator import ModelValidationError
from ..visual.class_diagram import build_class_diagram
from ..visual.export import save_all_diagrams, save_image
from ..visual.layout import DrawList
from ..visual.state_diagram import build_state_diagram
from .panels import (
    PALETTE,
    DiagramCanvasPanel,
    ErrorPanel,
    JavaPreviewPanel,
    JsonEditorPanel,
    StateDiagramPanel,
    get_ui_family,
)

EXAMPLE_PATH = Path(__file__).resolve().parents[3] / "models" / "parking_gate.json"


class XtumlApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("xtuml2java — xtUML to Java 17 Model Compiler")
        self.geometry("1420x860")
        self.minsize(1080, 680)
        self.configure(bg=PALETTE["bg_app"])

        self.model: Optional[Model] = None
        self.project: Optional[GeneratedProject] = None
        self.class_dl: Optional[DrawList] = None
        self.state_dls: Dict[str, DrawList] = {}

        self._configure_styles()
        self._build()
        self.load_example(silent=True)

    # ------------------------------------------------------------------ Tema & Styling
    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        ui_font = get_ui_family(self)
        style.configure(".", font=(ui_font, 9), background=PALETTE["bg_app"], foreground=PALETTE["text_primary"])

        # Tombol Primer (Indigo)
        style.configure(
            "Primary.TButton",
            font=(ui_font, 9, "bold"),
            background=PALETTE["accent"],
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(14, 7),
        )
        style.map(
            "Primary.TButton",
            background=[("active", PALETTE["accent_hover"]), ("disabled", "#93C5FD")],
            foreground=[("disabled", "#EFF6FF")],
        )

        # Tombol Sekunder / Toolbar
        style.configure(
            "Subtle.TButton",
            font=(ui_font, 9),
            background=PALETTE["bg_card"],
            foreground=PALETTE["text_primary"],
            bordercolor=PALETTE["border"],
            lightcolor=PALETTE["bg_card"],
            darkcolor=PALETTE["bg_card"],
            borderwidth=1,
            padding=(10, 6),
        )
        style.map(
            "Subtle.TButton",
            background=[("active", PALETTE["bg_subtle"]), ("disabled", PALETTE["bg_subtle"])],
            foreground=[("disabled", PALETTE["text_muted"])],
        )

        # Notebook & Tabs
        style.configure("Modern.TNotebook", background=PALETTE["bg_app"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure(
            "Modern.TNotebook.Tab",
            font=(ui_font, 9, "bold"),
            background=PALETTE["bg_subtle"],
            foreground=PALETTE["text_secondary"],
            padding=(16, 8),
            borderwidth=0,
        )
        style.map(
            "Modern.TNotebook.Tab",
            background=[("selected", PALETTE["bg_card"]), ("active", "#E2E8F0")],
            foreground=[("selected", PALETTE["accent"]), ("active", PALETTE["text_primary"])],
        )

        # Treeview Error Panel
        style.configure(
            "Treeview",
            font=(ui_font, 9),
            background=PALETTE["bg_card"],
            fieldbackground=PALETTE["bg_card"],
            foreground=PALETTE["text_primary"],
            rowheight=28,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            font=(ui_font, 9, "bold"),
            background=PALETTE["bg_subtle"],
            foreground=PALETTE["text_secondary"],
            borderwidth=0,
            padding=(8, 6),
        )

        # PanedWindow sash
        style.configure("TPanedwindow", background=PALETTE["bg_app"])
        style.configure("Sash", sashthickness=6, sashrelief="flat", background=PALETTE["bg_app"])

    # ------------------------------------------------------------------ Layout UI
    def _build(self) -> None:
        ui_font = get_ui_family(self)

        # Top Header Bar
        topbar = tk.Frame(self, bg=PALETTE["bg_card"], padx=16, pady=10)
        topbar.pack(fill="x")

        # Brand title
        brand = tk.Frame(topbar, bg=PALETTE["bg_card"])
        brand.pack(side="left")
        tk.Label(
            brand,
            text="xtuml2java",
            bg=PALETTE["bg_card"],
            fg=PALETTE["text_primary"],
            font=(ui_font, 12, "bold"),
        ).pack(side="left")
        tk.Label(
            brand,
            text="  Model Compiler",
            bg=PALETTE["bg_card"],
            fg=PALETTE["text_muted"],
            font=(ui_font, 10),
        ).pack(side="left", pady=(2, 0))

        # Action group kanan: Simpan & Export
        right_actions = tk.Frame(topbar, bg=PALETTE["bg_card"])
        right_actions.pack(side="right")

        self.btn_save = ttk.Button(
            right_actions, text="Simpan Java…", style="Subtle.TButton", command=self.save_java, state="disabled"
        )
        self.btn_save.pack(side="left", padx=3)

        self.btn_exp = ttk.Button(
            right_actions, text="Export Diagram Aktif…", style="Subtle.TButton", command=self.export_active, state="disabled"
        )
        self.btn_exp.pack(side="left", padx=3)

        self.btn_exp_all = ttk.Button(
            right_actions, text="Export Semua Diagram…", style="Subtle.TButton", command=self.export_all, state="disabled"
        )
        self.btn_exp_all.pack(side="left", padx=(3, 0))

        # Action group tengah: Buka, Contoh, Compile
        center_actions = tk.Frame(topbar, bg=PALETTE["bg_card"])
        center_actions.pack(side="right", padx=(0, 18))

        ttk.Button(center_actions, text="Buka JSON…", style="Subtle.TButton", command=self.open_json).pack(side="left", padx=3)
        ttk.Button(center_actions, text="Muat Contoh Parkir", style="Subtle.TButton", command=self.load_example).pack(side="left", padx=3)
        ttk.Button(center_actions, text="▶  Compile", style="Primary.TButton", command=self.compile).pack(side="left", padx=(10, 0))

        # Garis pemisah header
        tk.Frame(self, height=1, bg=PALETTE["border"]).pack(fill="x")

        # Main Workspace (Split Pane)
        workspace = tk.Frame(self, bg=PALETTE["bg_app"], padx=14, pady=12)
        workspace.pack(fill="both", expand=True)

        pane = ttk.PanedWindow(workspace, orient="horizontal")
        pane.pack(fill="both", expand=True)

        self.editor = JsonEditorPanel(pane)
        pane.add(self.editor, weight=2)

        right_card = tk.Frame(pane, bg=PALETTE["bg_card"], highlightthickness=1, highlightbackground=PALETTE["border"])
        pane.add(right_card, weight=3)

        self.tabs = ttk.Notebook(right_card, style="Modern.TNotebook")
        self.tabs.pack(fill="both", expand=True)

        self.class_panel = DiagramCanvasPanel(self.tabs)
        self.state_panel = StateDiagramPanel(self.tabs)
        self.java_panel = JavaPreviewPanel(self.tabs)
        self.error_panel = ErrorPanel(self.tabs)

        self.tabs.add(self.class_panel, text="  Class Diagram  ")
        self.tabs.add(self.state_panel, text="  State Diagram  ")
        self.tabs.add(self.java_panel, text="  Kode Java  ")
        self.tabs.add(self.error_panel, text="  Log & Error  ")

        # Bottom Status Bar dengan Badge Indikator
        tk.Frame(self, height=1, bg=PALETTE["border"]).pack(fill="x", side="bottom")
        statusbar = tk.Frame(self, bg=PALETTE["bg_card"], padx=14, pady=6)
        statusbar.pack(fill="x", side="bottom")

        self.badge_var = tk.StringVar(value="SIAP")
        self.badge_lbl = tk.Label(
            statusbar,
            textvariable=self.badge_var,
            bg=PALETTE["accent_soft"],
            fg=PALETTE["accent"],
            font=(ui_font, 8, "bold"),
            padx=8,
            pady=2,
        )
        self.badge_lbl.pack(side="left", padx=(0, 10))

        self.status = tk.StringVar(value="Muat model JSON lalu tekan Compile (Ctrl+Enter).")
        tk.Label(
            statusbar,
            textvariable=self.status,
            bg=PALETTE["bg_card"],
            fg=PALETTE["text_secondary"],
            font=(ui_font, 9),
        ).pack(side="left")

        tk.Label(
            statusbar,
            text="Shortcut: Ctrl + Enter untuk Compile",
            bg=PALETTE["bg_card"],
            fg=PALETTE["text_muted"],
            font=(ui_font, 8),
        ).pack(side="right")

        self.bind("<Control-Return>", lambda _e: self.compile())

    def _set_status(self, message: str, state: str = "info") -> None:
        self.status.set(message)
        if state == "ok":
            self.badge_var.set("BERHASIL")
            self.badge_lbl.configure(bg=PALETTE["success_soft"], fg=PALETTE["success"])
        elif state == "error":
            self.badge_var.set("ERROR")
            self.badge_lbl.configure(bg=PALETTE["danger_soft"], fg=PALETTE["danger"])
        else:
            self.badge_var.set("SIAP")
            self.badge_lbl.configure(bg=PALETTE["accent_soft"], fg=PALETTE["accent"])

    def _set_actions(self, enabled: bool) -> None:
        st = "normal" if enabled else "disabled"
        for b in (self.btn_save, self.btn_exp, self.btn_exp_all):
            b.configure(state=st)

    # ------------------------------------------------------------------ Aksi
    def open_json(self) -> None:
        path = filedialog.askopenfilename(title="Buka model JSON", filetypes=[("JSON", "*.json"), ("Semua berkas", "*.*")])
        if not path:
            return
        try:
            self.editor.set_text(Path(path).read_text(encoding="utf-8"))
            self._set_status(f"Berkas dimuat: {path}", "info")
        except OSError as ex:
            messagebox.showerror("Gagal membuka berkas", str(ex))

    def load_example(self, silent: bool = False) -> None:
        try:
            self.editor.set_text(EXAMPLE_PATH.read_text(encoding="utf-8"))
            if not silent:
                self._set_status("Contoh Automated Parking Gate System dimuat.", "info")
        except OSError:
            if not silent:
                messagebox.showwarning("Contoh tidak ditemukan", f"Tidak dapat membaca {EXAMPLE_PATH}")

    def compile(self) -> None:
        """Pipa kompilasi in-memory. Tidak menulis apa pun ke disk."""
        self._set_actions(False)
        self.model = self.project = self.class_dl = None
        try:
            result = load_from_text(self.editor.get_text())
            if not result.ok:
                self._show_failure(result.errors)
                return
            self.model = result.model
            self.project = generate_project(self.model)
            self.class_dl = build_class_diagram(self.model)
            self.state_dls = {
                c.name: build_state_diagram(c.state_machine, c.name)
                for c in self.model.classes
                if c.state_machine is not None
            }
        except Exception as ex:
            self._show_failure([ModelValidationError("$", f"kesalahan internal: {ex}")])
            traceback.print_exc()
            return

        self.class_panel.show(self.class_dl)
        self.state_panel.set_diagrams(self.state_dls)
        self.java_panel.set_files(self.project.files, preferred="Main.java")
        self.error_panel.show_errors(
            result.errors,
            self.project.todos,
            f"Compile berhasil: {len(self.project.files)} file Java, {len(self.state_dls)} state diagram.",
        )
        self._set_actions(True)
        self._set_status(
            f"Package '{self.model.package}' siap ({len(self.project.files)} file Java). Klik Simpan/Export untuk menulis ke disk.",
            "ok",
        )
        self.tabs.select(self.class_panel)

        # ... di dalam method compile():
        runtime_names = {f"{name}.java" for name in RUNTIME_FILES}
        generated_only = {k: v for k, v in self.project.files.items() if k not in runtime_names}
        self.java_panel.set_files(generated_only, preferred="Main.java")

    def _show_failure(self, errors: List[ModelValidationError]) -> None:
        self.class_panel.show(None)
        self.state_panel.set_diagrams({})
        self.java_panel.set_files({})
        self.error_panel.show_errors(errors)
        self.tabs.select(self.error_panel)
        n_err = sum(1 for e in errors if e.severity == "error")
        self._set_status(f"Compile gagal dengan {n_err} error. Periksa tab Log & Error.", "error")

    def save_java(self) -> None:
        if not self.project:
            return
        folder = filedialog.askdirectory(title="Pilih folder keluaran (mis. out/)")
        if not folder:
            return
        try:
            written = write_project(self.project, folder)
        except OSError as ex:
            messagebox.showerror("Gagal menyimpan", str(ex))
            return
        self._set_status(f"{len(written)} file .java disimpan di {written[0].parent}", "ok")
        messagebox.showinfo(
            "Tersimpan",
            f"{len(written)} file disimpan di:\n{written[0].parent}\n\n"
            f"Kompilasi: javac {written[0].parent.name}/*.java\nJalankan: java {self.project.package}.Main",
        )

    def export_active(self) -> None:
        idx = self.tabs.index(self.tabs.select())
        if idx == 1 and self.state_panel.current is not None:
            dl, base = self.state_panel.current, f"state_{self.state_panel.current_name}"
        elif self.class_dl is not None:
            dl, base = self.class_dl, "class_diagram"
        else:
            return
        path = filedialog.asksaveasfilename(
            title="Export diagram",
            initialfile=base,
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
        )
        if not path:
            return
        try:
            save_image(dl, path)
            self._set_status(f"Diagram diekspor ke: {path}", "ok")
        except Exception as ex:
            messagebox.showerror("Gagal export", str(ex))

    def export_all(self) -> None:
        if not self.model:
            return
        folder = filedialog.askdirectory(title="Pilih folder untuk semua diagram")
        if not folder:
            return
        fmt = "png" if messagebox.askyesno("Format", "Gunakan PNG?\n(Pilih 'No' untuk JPG)") else "jpg"
        try:
            files = save_all_diagrams(self.model, folder, fmt)
            self._set_status(f"{len(files)} gambar diekspor ke {folder}", "ok")
        except Exception as ex:
            messagebox.showerror("Gagal export", str(ex))


def run_gui() -> int:
    app = XtumlApp()
    app.mainloop()
    return 0