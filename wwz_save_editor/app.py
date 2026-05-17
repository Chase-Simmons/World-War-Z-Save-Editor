"""Tkinter GUI for editing WWZ save data."""
from __future__ import annotations

import datetime
import json
import os
import shutil
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Per-monitor DPI awareness on Windows — otherwise Tk scales fonts but not widget sizes,
# leaving content larger than the window allotted for it.
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from . import saves, tabs

APP_NAME = "WWZ Save Editor"
CONFIG_DIR = Path(os.getenv("APPDATA") or str(Path.home())) / "wwz-save-editor"
CONFIG_PATH = CONFIG_DIR / "config.json"

# Color palette
BG = "#f5f5f7"
CARD = "#ffffff"
TEXT = "#1d1d1f"
HINT = "#6e6e73"
BORDER = "#d1d1d6"
ACCENT = "#0a7aff"
ACCENT_HOVER = "#0051d5"
ACCENT_ACTIVE = "#003d99"
DANGER = "#ff3b30"
DANGER_HOVER = "#cc2f26"


def default_save_folder() -> Path | None:
    candidate = Path(os.getenv("LOCALAPPDATA", "")) / "Saber" / "WWZ" / "client" / "storage"
    return candidate if candidate.exists() else None


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    except Exception:
        pass


def _apply_style(root: tk.Tk) -> None:
    """Configure ttk styles for a cleaner modern look."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    base_font = ("Segoe UI", 10)
    bold_font = ("Segoe UI Semibold", 10)
    header_font = ("Segoe UI Semibold", 14)
    col_header_font = ("Segoe UI Semibold", 9)

    root.option_add("*Font", base_font)
    root.configure(background=BG)

    style.configure(".", background=BG, foreground=TEXT, font=base_font)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD, relief="solid", borderwidth=1, bordercolor=BORDER)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Hint.TLabel", background=BG, foreground=HINT, font=("Segoe UI", 9))
    style.configure("Header.TLabel", background=BG, foreground=TEXT, font=header_font)
    style.configure("ColHeader.TLabel", background=CARD, foreground=HINT, font=col_header_font)
    style.configure("Label.TLabel", background=BG, foreground=TEXT, font=bold_font)
    style.configure("Status.TLabel", background=BG, foreground=HINT, font=("Segoe UI", 9))

    style.configure("TButton", background="#ffffff", foreground=TEXT, padding=(12, 6),
                    borderwidth=1, relief="solid", focusthickness=0)
    style.map("TButton",
              background=[("active", "#f0f0f4"), ("pressed", "#e0e0e6")],
              bordercolor=[("active", BORDER)])

    style.configure("Primary.TButton", background=ACCENT, foreground="#ffffff",
                    padding=(14, 7), borderwidth=0, focusthickness=0)
    style.map("Primary.TButton",
              background=[("active", ACCENT_HOVER), ("pressed", ACCENT_ACTIVE)],
              foreground=[("disabled", "#cccccc")])

    style.configure("Danger.TButton", background=DANGER, foreground="#ffffff",
                    padding=(14, 7), borderwidth=0, focusthickness=0)
    style.map("Danger.TButton",
              background=[("active", DANGER_HOVER), ("pressed", "#a02520")])

    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(4, 6, 4, 0))
    style.configure("TNotebook.Tab", background="#e6e6eb", foreground=TEXT,
                    padding=(16, 8), borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", CARD), ("active", "#f0f0f4")],
              foreground=[("selected", TEXT)],
              expand=[("selected", (0, 0, 0, 0))])

    style.configure("TEntry", fieldbackground=CARD, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=4)
    style.configure("TSpinbox", fieldbackground=CARD, foreground=TEXT,
                    bordercolor=BORDER, arrowsize=12, padding=4)
    style.configure("TCombobox", fieldbackground=CARD, foreground=TEXT,
                    bordercolor=BORDER, padding=4)
    style.map("TCombobox", fieldbackground=[("readonly", CARD)])

    style.configure("TCheckbutton", background=CARD, foreground=TEXT)
    style.map("TCheckbutton", background=[("active", "#f5f5f7")])

    style.configure("TScrollbar", background=BG, troughcolor=BG, borderwidth=0)

    style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                    rowheight=24, borderwidth=0)
    style.configure("Treeview.Heading", background=BG, foreground=TEXT, font=col_header_font,
                    borderwidth=0)


class WwzSaveEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1280x960")
        self.minsize(1040, 700)
        _apply_style(self)

        self._cfg = load_config()
        self._save_folder: Path | None = None
        self.slots: list[saves.SaveSlot] = []
        self.current_slot: saves.SaveSlot | None = None

        self._build_ui()
        self._restore_state()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<Control-s>", lambda _e: self._save_all())

    # ----- UI -----
    def _build_ui(self) -> None:
        # ----- Header row -----
        header = ttk.Frame(self, padding=(18, 14, 18, 8))
        header.pack(fill="x", side="top")
        ttk.Label(header, text="WWZ Save Editor", style="Header.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )

        ttk.Label(header, text="Save folder", style="Label.TLabel").grid(row=1, column=0, sticky="w")
        self._folder_var = tk.StringVar()
        ttk.Entry(header, textvariable=self._folder_var).grid(row=1, column=1, sticky="ew", padx=10)
        ttk.Button(header, text="Browse…", command=self._browse_folder).grid(row=1, column=2, padx=2)
        ttk.Button(header, text="Reload", command=self._reload_folder).grid(row=1, column=3, padx=2)

        ttk.Label(header, text="Save slot", style="Label.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self._slot_var = tk.StringVar()
        self._slot_combo = ttk.Combobox(header, textvariable=self._slot_var, state="readonly")
        self._slot_combo.grid(row=2, column=1, columnspan=3, sticky="ew", padx=10, pady=(8, 0))
        self._slot_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_slot_changed())
        header.columnconfigure(1, weight=1)

        # ----- Status bar (bottom-most, packed first so notebook can't steal its space) -----
        status = ttk.Frame(self, padding=(18, 0, 18, 10))
        status.pack(fill="x", side="bottom")
        self._status_var = tk.StringVar(value="Pick a save folder to begin.")
        ttk.Label(status, textvariable=self._status_var, style="Status.TLabel", anchor="w").pack(fill="x")

        # ----- Footer / actions (above status) -----
        footer = ttk.Frame(self, padding=(18, 10, 18, 8))
        footer.pack(fill="x", side="bottom")
        ttk.Button(footer, text="Unlock & Max All", style="Danger.TButton",
                   command=self._unlock_and_max_everything).pack(side="left")
        ttk.Button(footer, text="Clear badges", command=self._clear_visited).pack(side="left", padx=8)
        self._save_btn = ttk.Button(
            footer, text="Save All  (Ctrl+S)", style="Primary.TButton",
            command=self._save_all, state="disabled",
        )
        self._save_btn.pack(side="right")
        ttk.Button(footer, text="Backups…", command=self._show_backups).pack(side="right", padx=8)
        ttk.Button(footer, text="Revert slot", command=self._revert_slot).pack(side="right")

        # ----- Tabs (packed LAST so expand=True only consumes the remainder) -----
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=18, pady=(6, 0))

        self._tab_classes = tabs.ClassesTab(self._notebook, self)
        self._tab_currency = tabs.CurrencyTab(self._notebook, self)
        self._tab_weapons = tabs.WeaponsTab(self._notebook, self)
        self._tab_rewards = tabs.RewardsTab(self._notebook, self)
        self._tab_cosmetics = tabs.CosmeticsTab(self._notebook, self)
        self._tab_advanced = tabs.AdvancedTab(self._notebook, self)
        self._all_tabs = [
            self._tab_classes, self._tab_currency, self._tab_weapons,
            self._tab_rewards, self._tab_cosmetics, self._tab_advanced,
        ]
        self._notebook.add(self._tab_classes, text="Classes")
        self._notebook.add(self._tab_currency, text="Currency")
        self._notebook.add(self._tab_weapons, text="Weapons")
        self._notebook.add(self._tab_rewards, text="Rewards")
        self._notebook.add(self._tab_cosmetics, text="Cosmetics")
        self._notebook.add(self._tab_advanced, text="Advanced")

    # ----- folder / slot -----
    def _restore_state(self) -> None:
        folder = self._cfg.get("save_folder")
        if not folder:
            d = default_save_folder()
            folder = str(d) if d else ""
        if folder:
            self._folder_var.set(folder)
            self._save_folder = Path(folder)
            self._reload_folder()
        geom = self._cfg.get("geometry")
        if geom:
            try:
                self.geometry(geom)
            except tk.TclError:
                pass

    def _on_close(self) -> None:
        if self._any_dirty() and not self._confirm_discard():
            return
        self._cfg["save_folder"] = str(self._save_folder) if self._save_folder else ""
        self._cfg["geometry"] = self.geometry()
        save_config(self._cfg)
        self.destroy()

    def _confirm_discard(self) -> bool:
        return messagebox.askyesno(APP_NAME, "You have unsaved changes. Discard them?")

    def _browse_folder(self) -> None:
        start = self._folder_var.get() or str(Path.home())
        chosen = filedialog.askdirectory(initialdir=start, title="Choose your WWZ save folder")
        if chosen:
            self._folder_var.set(chosen)
            self._save_folder = Path(chosen)
            self._reload_folder()

    def _reload_folder(self) -> None:
        folder_str = self._folder_var.get()
        if not folder_str:
            return
        folder = Path(folder_str)
        if not folder.exists():
            self.set_status(f"Folder not found: {folder}")
            return
        self._save_folder = folder
        self.slots = saves.discover_slots(folder)
        if not self.slots:
            self._slot_combo.configure(values=[])
            self._slot_var.set("")
            self.current_slot = None
            self.refresh_tabs()
            self._update_save_button()
            self.set_status(f"No save slots found under {folder}.")
            return
        labels = [self._label_for(i, s) for i, s in enumerate(self.slots)]
        self._slot_combo.configure(values=labels)
        prev = self._cfg.get("slot_folder")
        choice = 0
        for i, s in enumerate(self.slots):
            if str(s.folder) == prev:
                choice = i
                break
        self._slot_var.set(labels[choice])
        self.current_slot = self.slots[choice]
        self._cfg["slot_folder"] = str(self.current_slot.folder)
        self.refresh_tabs()
        self._update_save_button()
        self.set_status(f"Loaded {len(self.slots)} save slot(s).")

    def _label_for(self, idx: int, slot: saves.SaveSlot) -> str:
        try:
            mtime = max(f.path.stat().st_mtime for f in slot.files.values() if f.path.exists())
            stamp = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        except (OSError, ValueError):
            stamp = "?"
        label = f"Slot {idx + 1}  —  last modified {stamp}"
        if idx == 0:
            label += "  (most recent)"
        return label

    def _on_slot_changed(self) -> None:
        idx = self._slot_combo.current()
        if idx < 0 or idx >= len(self.slots):
            return
        new = self.slots[idx]
        if new is self.current_slot:
            return
        self.current_slot = new
        self._cfg["slot_folder"] = str(new.folder)
        self.refresh_tabs()
        self._update_save_button()

    # ----- tabs / dirty -----
    def refresh_tabs(self) -> None:
        for t in self._all_tabs:
            t.load(self.current_slot)

    def refresh_other_tabs(self, source: tk.Widget) -> None:
        for t in self._all_tabs:
            if t is not source:
                t.load(self.current_slot)

    def mark_dirty(self) -> None:
        self._update_save_button()

    def _any_dirty(self) -> bool:
        return any(s.dirty for s in self.slots)

    def _update_save_button(self) -> None:
        state = "normal" if (self.current_slot and self.current_slot.dirty) else "disabled"
        self._save_btn.configure(state=state)

    # ----- master actions -----
    def _unlock_and_max_everything(self) -> None:
        if not self.current_slot:
            messagebox.showinfo(APP_NAME, "No slot loaded.")
            return
        msg = (
            "This will modify the current slot in memory:\n\n"
            "  • Classes — Experience set to 50,000,000 and Prestige set to max on all 8 classes\n"
            "  • Currency — premium currency, coins, and account level maxed\n"
            "  • Weapons — every firearm set to level 15, XP 0\n"
            "  • Rewards — everything unlocked (main + community/Twitch/Redynx)\n"
            "  • Cosmetics — frames, accessories, outfits, portraits unlocked\n"
            "  • Clear every 'new' (isVisited) badge\n\n"
            "Class XP only converts to a higher level after you enter and exit a match "
            "(one level per match). Weapon levels apply directly.\n\n"
            "Nothing is written to disk until you press Save All. Continue?"
        )
        if not messagebox.askyesno(APP_NAME, msg):
            return

        self._tab_classes.max_all()
        self._tab_currency.max_all()
        self._tab_weapons.max_all()
        self._tab_rewards.unlock_all()
        self._tab_cosmetics.unlock_all()

        # Walk user_progression.dat and set every isVisited true
        f = self.current_slot.get("user_progression.dat")
        cleared = 0
        if f and f.doc is not None:
            cleared = tabs.set_all_visited(f.doc)
            if cleared:
                f.dirty = True
        # Same for user_firearms.dat
        f2 = self.current_slot.get("user_firearms.dat")
        if f2 and f2.doc is not None:
            extra = tabs.set_all_visited(f2.doc)
            if extra:
                f2.dirty = True
                cleared += extra

        self.refresh_tabs()
        self.mark_dirty()
        self.set_status(
            f"Applied: max XP + all unlocks + currency boost. Cleared {cleared} 'new' badges. "
            "Press Save All to write to disk."
        )

    def _clear_visited(self) -> None:
        if not self.current_slot:
            return
        total = 0
        for f in self.current_slot.files.values():
            if f.doc is not None:
                n = tabs.set_all_visited(f.doc)
                if n:
                    f.dirty = True
                    total += n
        if total == 0:
            self.set_status("Nothing to clear — all 'new' badges already cleared.")
            return
        self.refresh_tabs()
        self.mark_dirty()
        self.set_status(f"Cleared {total} 'new' badges across the slot.")

    # ----- save / revert -----
    def _save_all(self) -> None:
        if not self.current_slot or not self.current_slot.dirty:
            return
        try:
            written = saves.save_slot(self.current_slot)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Save failed:\n\n{e}")
            self.set_status(f"Save failed: {e}")
            return
        self._update_save_button()
        names = ", ".join(p.name for p in written)
        self.set_status(f"Saved: {names}.  Backups created.")

    def _revert_slot(self) -> None:
        if not self.current_slot or not self.current_slot.dirty:
            return
        if not messagebox.askyesno(APP_NAME, "Discard all unsaved changes in this slot?"):
            return
        self._reload_folder()

    # ----- backups -----
    def _show_backups(self) -> None:
        if not self.current_slot:
            return
        win = tk.Toplevel(self)
        win.title("Restore Backup")
        win.transient(self)
        win.geometry("640x460")
        win.configure(background=BG)

        ttk.Label(win, text="Pick a file:", padding=(14, 14, 14, 0)).pack(anchor="w")
        file_var = tk.StringVar()
        names = sorted(self.current_slot.files.keys())
        file_combo = ttk.Combobox(win, textvariable=file_var, state="readonly", values=names, width=42)
        file_combo.pack(anchor="w", padx=14, pady=6)
        ttk.Label(win, text="Backups (newest first):", padding=(14, 8, 14, 0)).pack(anchor="w")
        lb = tk.Listbox(win, background=CARD, foreground=TEXT, borderwidth=1, relief="solid",
                        highlightthickness=0, selectbackground=ACCENT, selectforeground="white")
        lb.pack(fill="both", expand=True, padx=14, pady=6)

        def refresh_list(_evt=None) -> None:
            lb.delete(0, "end")
            f = self.current_slot.get(file_var.get())
            if not f:
                return
            for b in saves.list_backups(f.path):
                lb.insert("end", b.name)

        file_combo.bind("<<ComboboxSelected>>", refresh_list)
        if "user_progression.dat" in self.current_slot.files:
            file_var.set("user_progression.dat")
            refresh_list()

        def do_restore() -> None:
            f = self.current_slot.get(file_var.get())
            sel = lb.curselection()
            if not f or not sel:
                return
            backups = saves.list_backups(f.path)
            src = backups[sel[0]]
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(f.path, f.path.with_name(f.path.name + f".bak_{ts}"))
            shutil.copy2(src, f.path)
            win.destroy()
            self._reload_folder()
            self.set_status(f"Restored {f.name} from {src.name}.")

        ttk.Button(win, text="Restore selected", style="Primary.TButton",
                   command=do_restore).pack(pady=12)

    def set_status(self, msg: str) -> None:
        self._status_var.set(msg)


def main() -> None:
    WwzSaveEditor().mainloop()


if __name__ == "__main__":
    main()
