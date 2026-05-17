"""Domain-specific edit tabs for the save editor."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from . import classes, saves


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def set_all_visited(obj: Any) -> int:
    """Recursively walk a JSON-like value and set every 'isVisited' field to True.

    Returns the number of fields actually changed.
    """
    changed = 0
    if isinstance(obj, dict):
        if "isVisited" in obj and obj["isVisited"] is not True:
            obj["isVisited"] = True
            changed += 1
        for v in obj.values():
            changed += set_all_visited(v)
    elif isinstance(obj, list):
        for item in obj:
            changed += set_all_visited(item)
    return changed


class ScrollFrame(ttk.Frame):
    """A vertically scrollable container. Pack/grid widgets into `self.inner`."""

    def __init__(self, master: tk.Widget, inner_style: str = "Card.TFrame",
                 canvas_bg: str = "#ffffff", **kw: Any) -> None:
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=canvas_bg)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner = ttk.Frame(self.canvas, style=inner_style)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", lambda _e: self._bind_wheel(True))
        self.canvas.bind("<Leave>", lambda _e: self._bind_wheel(False))

    def _on_inner_configure(self, _evt) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, evt) -> None:
        self.canvas.itemconfigure(self._window, width=evt.width)

    def _bind_wheel(self, active: bool) -> None:
        if active:
            self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        else:
            self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, evt) -> None:
        self.canvas.yview_scroll(-int(evt.delta / 120), "units")

    def clear(self) -> None:
        for w in self.inner.winfo_children():
            w.destroy()


def _section_header(parent: tk.Widget, text: str) -> ttk.Label:
    lbl = ttk.Label(parent, text=text, style="Header.TLabel")
    lbl.pack(anchor="w", pady=(0, 6))
    return lbl


def _hint(parent: tk.Widget, text: str) -> ttk.Label:
    lbl = ttk.Label(parent, text=text, style="Hint.TLabel", wraplength=900, justify="left")
    lbl.pack(anchor="w", pady=(0, 10))
    return lbl


# --------------------------------------------------------------------------- #
# Classes tab                                                                 #
# --------------------------------------------------------------------------- #
class ClassesTab(ttk.Frame):
    XP_DUMP = 50_000_000

    def __init__(self, parent: tk.Widget, app: Any) -> None:
        super().__init__(parent, padding=0)
        self.app = app
        self._vars: list[dict[str, tk.StringVar]] = []
        self._spins: list[dict[str, ttk.Spinbox]] = []
        self._active_var = tk.StringVar()
        self._loading = False
        self._scroll = ScrollFrame(self, inner_style="TFrame", canvas_bg="#f5f5f7")
        self._scroll.pack(fill="both", expand=True)
        self._content = ttk.Frame(self._scroll.inner, padding=18)
        self._content.pack(fill="both", expand=True)
        self._build()

    def _build(self) -> None:
        c = self._content
        _section_header(c, "Class progression")
        _hint(
            c,
            "Level is recomputed by the game from XP — it can't be set directly, so the Level "
            "field is disabled. Set Experience instead; the game will rank you up the next "
            "time you enter and exit a match (one level per match). Prestige is independent.",
        )

        row = ttk.Frame(c)
        row.pack(fill="x", pady=(0, 14))
        ttk.Label(row, text="Active class:", style="Label.TLabel").pack(side="left")
        self._active_combo = ttk.Combobox(
            row, textvariable=self._active_var, values=classes.CLASS_NAMES,
            state="readonly", width=18,
        )
        self._active_combo.pack(side="left", padx=10)
        self._active_combo.bind("<<ComboboxSelected>>", self._on_active_changed)

        table = ttk.Frame(c, style="Card.TFrame", padding=10)
        table.pack(fill="x")
        headers = ["Class", f"Level (1–{classes.MAX_LEVEL})", f"Prestige (0–{classes.MAX_PRESTIGE + 1})", "Experience"]
        for col, txt in enumerate(headers):
            ttk.Label(table, text=txt, style="ColHeader.TLabel").grid(
                row=0, column=col, padx=6, pady=(0, 10), sticky="w"
            )

        for i, name in enumerate(classes.CLASS_NAMES):
            ttk.Label(table, text=name, anchor="w", width=16).grid(
                row=i + 1, column=0, padx=6, pady=4, sticky="w"
            )
            vrow: dict[str, tk.StringVar] = {}
            srow: dict[str, ttk.Spinbox] = {}
            for col, (key, frm, to, w) in enumerate(
                [
                    ("level", classes.MIN_LEVEL, classes.MAX_LEVEL, 6),
                    ("prestige", 0, classes.MAX_PRESTIGE + 1, 6),
                    ("experience", 0, 999_999_999, 14),
                ],
                start=1,
            ):
                v = tk.StringVar()
                v.trace_add("write", lambda *_a, idx=i, k=key: self._on_changed(idx, k))
                sb = ttk.Spinbox(table, from_=frm, to=to, width=w, textvariable=v)
                sb.grid(row=i + 1, column=col, padx=6, pady=4, sticky="w")
                vrow[key] = v
                srow[key] = sb
            self._vars.append(vrow)
            self._spins.append(srow)

        actions = ttk.Frame(c)
        actions.pack(fill="x", pady=(18, 0))
        ttk.Button(actions, text="Max all classes", style="Primary.TButton",
                   command=self.max_all).pack(side="left")
        ttk.Button(actions, text="Set all XP to 0", command=self._reset_xp).pack(side="left", padx=10)

    def load(self, slot: saves.SaveSlot | None) -> None:
        self._loading = True
        try:
            perks = self._perks(slot)
            self._active_combo.configure(state="readonly" if perks else "disabled")
            if perks is None:
                for srow in self._spins:
                    for sb in srow.values():
                        sb.configure(state="disabled")
                for vrow in self._vars:
                    for v in vrow.values():
                        v.set("")
                self._active_var.set("")
                return
            active_idx = int(perks.get("active", 0))
            if 0 <= active_idx < len(classes.CLASS_NAMES):
                self._active_var.set(classes.CLASS_NAMES[active_idx])
            data = perks.get("data", [])
            for i in range(len(classes.CLASS_NAMES)):
                vrow = self._vars[i]
                srow = self._spins[i]
                if i < len(data):
                    e = data[i]
                    vrow["level"].set(str(e.get("level", 1)))
                    vrow["prestige"].set(str(e.get("prestige", -1) + 1))
                    vrow["experience"].set(str(e.get("experience", 0)))
                    srow["prestige"].configure(state="normal")
                    srow["experience"].configure(state="normal")
                    # Level can never be set directly — disable it.
                    srow["level"].configure(state="disabled")
                else:
                    for v in vrow.values():
                        v.set("")
                    for sb in srow.values():
                        sb.configure(state="disabled")
        finally:
            self._loading = False

    def _perks(self, slot: saves.SaveSlot | None) -> dict | None:
        if not slot:
            return None
        f = slot.get("user_progression.dat")
        if not f or f.doc is None:
            return None
        try:
            return f.doc["UserProgression"]["PVE"]["perksProgressionJson"]
        except (KeyError, TypeError):
            return None

    def _on_changed(self, idx: int, key: str) -> None:
        if self._loading:
            return
        slot = self.app.current_slot
        perks = self._perks(slot)
        if perks is None:
            return
        data = perks.get("data", [])
        if idx >= len(data):
            return
        try:
            ui_value = int(self._vars[idx][key].get())
        except ValueError:
            return
        stored = ui_value - 1 if key == "prestige" else ui_value
        if data[idx].get(key) == stored:
            return
        data[idx][key] = stored
        slot.get("user_progression.dat").dirty = True
        self.app.mark_dirty()

    def _on_active_changed(self, _evt) -> None:
        if self._loading:
            return
        slot = self.app.current_slot
        perks = self._perks(slot)
        if perks is None:
            return
        try:
            new_idx = classes.CLASS_NAMES.index(self._active_var.get())
        except ValueError:
            return
        if perks.get("active") == new_idx:
            return
        perks["active"] = new_idx
        slot.get("user_progression.dat").dirty = True
        self.app.mark_dirty()

    def max_all(self) -> None:
        """Set XP huge AND prestige to max on all classes."""
        for vrow in self._vars:
            if vrow["experience"].get():
                vrow["experience"].set(str(self.XP_DUMP))
            if vrow["prestige"].get():
                vrow["prestige"].set(str(classes.MAX_PRESTIGE + 1))

    def _reset_xp(self) -> None:
        for vrow in self._vars:
            if vrow["experience"].get():
                vrow["experience"].set("0")


# --------------------------------------------------------------------------- #
# Currency tab                                                                #
# --------------------------------------------------------------------------- #
class CurrencyTab(ttk.Frame):
    FIELDS = [
        ("currency", "Premium currency", 0, 999_999_999),
        ("coins", "Coins", 0, 999_999_999),
        ("level", "Account level", 0, 9999),
        ("episodesOwn", "Episodes owned", 0, 9999),
    ]
    MAX_VALUES = {"currency": 999_999_999, "coins": 999_999, "level": 999}

    def __init__(self, parent: tk.Widget, app: Any) -> None:
        super().__init__(parent, padding=0)
        self.app = app
        self._loading = False
        self._vars: dict[str, tk.StringVar] = {}
        self._frame_var = tk.StringVar()
        self._frame_combo: ttk.Combobox | None = None
        self._scroll = ScrollFrame(self, inner_style="TFrame", canvas_bg="#f5f5f7")
        self._scroll.pack(fill="both", expand=True)
        self._content = ttk.Frame(self._scroll.inner, padding=18)
        self._content.pack(fill="both", expand=True)
        self._build()

    def _build(self) -> None:
        c = self._content
        _section_header(c, "Currency & account")
        _hint(c, "Account-wide values. Saved in user_progression.dat → Shared.sharedProgressionJson.")

        form = ttk.Frame(c, style="Card.TFrame", padding=14)
        form.pack(anchor="w")
        for r, (key, label, lo, hi) in enumerate(self.FIELDS):
            ttk.Label(form, text=label, width=22, anchor="w").grid(row=r, column=0, padx=6, pady=6, sticky="w")
            v = tk.StringVar()
            v.trace_add("write", lambda *_a, k=key: self._on_changed(k))
            self._vars[key] = v
            sb = ttk.Spinbox(form, from_=lo, to=hi, width=16, textvariable=v)
            sb.grid(row=r, column=1, padx=6, pady=6, sticky="w")

        ttk.Label(form, text="Selected icon frame", width=22, anchor="w").grid(
            row=len(self.FIELDS), column=0, padx=6, pady=6, sticky="w"
        )
        self._frame_combo = ttk.Combobox(form, textvariable=self._frame_var, state="readonly", width=34)
        self._frame_combo.grid(row=len(self.FIELDS), column=1, padx=6, pady=6, sticky="w")
        self._frame_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_frame_changed())

        actions = ttk.Frame(c)
        actions.pack(fill="x", pady=(18, 0))
        ttk.Button(actions, text="Max currency + coins + level",
                   style="Primary.TButton", command=self.max_all).pack(side="left")

    def load(self, slot: saves.SaveSlot | None) -> None:
        self._loading = True
        try:
            shared = self._shared(slot)
            if shared is None:
                for v in self._vars.values():
                    v.set("")
                self._frame_var.set("")
                if self._frame_combo:
                    self._frame_combo.configure(values=[], state="disabled")
                return
            for key, *_ in self.FIELDS:
                self._vars[key].set(str(shared.get(key, 0)))
            frames = self._available_frames(slot)
            if self._frame_combo:
                self._frame_combo.configure(values=frames, state="readonly")
            self._frame_var.set(str(shared.get("currentIconFrame", "Empty")))
        finally:
            self._loading = False

    def _shared(self, slot: saves.SaveSlot | None) -> dict | None:
        if not slot:
            return None
        f = slot.get("user_progression.dat")
        if not f or f.doc is None:
            return None
        try:
            return f.doc["UserProgression"]["Shared"]["sharedProgressionJson"]
        except (KeyError, TypeError):
            return None

    def _available_frames(self, slot: saves.SaveSlot) -> list[str]:
        f = slot.get("user_progression.dat")
        if not f or f.doc is None:
            return ["Empty"]
        try:
            d = f.doc["UserProgression"]["IconFrames"]["iconFramesProgressionJson"]
        except (KeyError, TypeError):
            return ["Empty"]
        frames = [k for k, v in d.items() if isinstance(v, dict) and "isUnlocked" in v]
        return ["Empty"] + sorted(frames)

    def _on_changed(self, key: str) -> None:
        if self._loading:
            return
        slot = self.app.current_slot
        shared = self._shared(slot)
        if shared is None:
            return
        try:
            value = int(self._vars[key].get())
        except ValueError:
            return
        if shared.get(key) == value:
            return
        shared[key] = value
        slot.get("user_progression.dat").dirty = True
        self.app.mark_dirty()

    def _on_frame_changed(self) -> None:
        if self._loading:
            return
        slot = self.app.current_slot
        shared = self._shared(slot)
        if shared is None:
            return
        new = self._frame_var.get()
        if shared.get("currentIconFrame") == new:
            return
        shared["currentIconFrame"] = new
        slot.get("user_progression.dat").dirty = True
        self.app.mark_dirty()

    def max_all(self) -> None:
        for key, val in self.MAX_VALUES.items():
            if key in self._vars:
                self._vars[key].set(str(val))


# --------------------------------------------------------------------------- #
# Weapons tab                                                                 #
# --------------------------------------------------------------------------- #
class WeaponsTab(ttk.Frame):
    MAX_LEVEL = 15

    def __init__(self, parent: tk.Widget, app: Any) -> None:
        super().__init__(parent, padding=18)
        self.app = app
        self._loading = False
        self._rows: dict[str, dict[str, Any]] = {}
        self._filter_var = tk.StringVar()
        self._scroll: ScrollFrame | None = None
        self._build()

    def _build(self) -> None:
        _section_header(self, "Weapons")
        _hint(
            self,
            f"Each firearm has a level (1–{self.MAX_LEVEL}) and XP. Both are directly editable. "
            "Saved in user_firearms.dat.",
        )

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Filter:").pack(side="left")
        ttk.Entry(bar, textvariable=self._filter_var, width=26).pack(side="left", padx=8)
        self._filter_var.trace_add("write", lambda *_a: self._apply_filter())
        ttk.Button(bar, text=f"Max level (visible)", style="Primary.TButton",
                   command=self.max_visible).pack(side="right")
        ttk.Button(bar, text="Reset XP (visible)", command=self._reset_xp).pack(side="right", padx=8)

        self._scroll = ScrollFrame(self)
        self._scroll.pack(fill="both", expand=True)

    def load(self, slot: saves.SaveSlot | None) -> None:
        self._loading = True
        try:
            assert self._scroll is not None
            self._scroll.clear()
            self._rows.clear()
            firearms = self._firearms(slot)
            if firearms is None:
                ttk.Label(self._scroll.inner, text="(No firearms file in this slot.)", padding=20).pack()
                return
            inner = self._scroll.inner
            ttk.Label(inner, text="Firearm", style="ColHeader.TLabel").grid(row=0, column=0, padx=8, pady=(8, 8), sticky="w")
            ttk.Label(inner, text=f"Level (1–{self.MAX_LEVEL})", style="ColHeader.TLabel").grid(row=0, column=1, padx=8, pady=(8, 8), sticky="w")
            ttk.Label(inner, text="XP", style="ColHeader.TLabel").grid(row=0, column=2, padx=8, pady=(8, 8), sticky="w")

            for r, name in enumerate(sorted(firearms.keys()), start=1):
                entry = firearms[name]
                name_lbl = ttk.Label(inner, text=name, anchor="w", width=34)
                name_lbl.grid(row=r, column=0, padx=8, pady=3, sticky="w")

                lvl_var = tk.StringVar(value=str(entry.get("level", 1)))
                xp_var = tk.StringVar(value=str(entry.get("levelXp", 0)))
                lvl_var.trace_add("write", lambda *_a, n=name: self._on_change(n, "level"))
                xp_var.trace_add("write", lambda *_a, n=name: self._on_change(n, "levelXp"))
                lvl_sb = ttk.Spinbox(inner, from_=1, to=self.MAX_LEVEL, width=6, textvariable=lvl_var)
                lvl_sb.grid(row=r, column=1, padx=8, pady=3, sticky="w")
                xp_sb = ttk.Spinbox(inner, from_=0, to=999_999_999, width=14, textvariable=xp_var)
                xp_sb.grid(row=r, column=2, padx=8, pady=3, sticky="w")

                self._rows[name] = {
                    "level": lvl_var, "levelXp": xp_var,
                    "_name_widget": name_lbl, "_lvl_widget": lvl_sb, "_xp_widget": xp_sb,
                }
        finally:
            self._loading = False

    def _firearms(self, slot: saves.SaveSlot | None) -> dict | None:
        if not slot:
            return None
        f = slot.get("user_firearms.dat")
        if not f or f.doc is None:
            return None
        try:
            return f.doc["UserFirearms"]["firearmsProgressionRevampJson"]["firearms"]
        except (KeyError, TypeError):
            return None

    def _on_change(self, name: str, key: str) -> None:
        if self._loading:
            return
        slot = self.app.current_slot
        firearms = self._firearms(slot)
        if firearms is None or name not in firearms:
            return
        try:
            value = int(self._rows[name][key].get())
        except ValueError:
            return
        if firearms[name].get(key) == value:
            return
        firearms[name][key] = value
        slot.get("user_firearms.dat").dirty = True
        self.app.mark_dirty()

    def _apply_filter(self) -> None:
        needle = self._filter_var.get().lower().strip()
        for name, row in self._rows.items():
            visible = (needle in name.lower()) if needle else True
            for w in (row["_name_widget"], row["_lvl_widget"], row["_xp_widget"]):
                if visible:
                    w.grid()
                else:
                    w.grid_remove()

    def max_visible(self) -> None:
        for name, row in self._rows.items():
            if row["_name_widget"].winfo_ismapped():
                row["level"].set(str(self.MAX_LEVEL))
                row["levelXp"].set("0")

    def _reset_xp(self) -> None:
        for name, row in self._rows.items():
            if row["_name_widget"].winfo_ismapped():
                row["levelXp"].set("0")

    def max_all(self) -> None:
        """Ignores the filter — used by Unlock & Max Everything."""
        for row in self._rows.values():
            row["level"].set(str(self.MAX_LEVEL))
            row["levelXp"].set("0")


# --------------------------------------------------------------------------- #
# Unlock-list subtab (Frames / Accessories / Rewards / Community)             #
# --------------------------------------------------------------------------- #
class _UnlockListSubTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: Any, title: str,
                 path: tuple[str, ...], flag_key: str) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self._title = title
        self._path = path
        self._flag = flag_key
        self._loading = False
        self._vars: dict[str, tk.BooleanVar] = {}
        self._widgets: dict[str, tk.Widget] = {}
        self._filter_var = tk.StringVar()
        self._build()

    def _build(self) -> None:
        _hint(self, f"{self._title}. Toggle individually, filter, or use bulk actions.")

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Filter:").pack(side="left")
        ttk.Entry(bar, textvariable=self._filter_var, width=26).pack(side="left", padx=8)
        self._filter_var.trace_add("write", lambda *_a: self._apply_filter())
        ttk.Button(bar, text="Unlock all (visible)", style="Primary.TButton",
                   command=lambda: self._set_visible(True)).pack(side="right")
        ttk.Button(bar, text="Lock all (visible)",
                   command=lambda: self._set_visible(False)).pack(side="right", padx=8)

        self._scroll = ScrollFrame(self)
        self._scroll.pack(fill="both", expand=True)

    def load(self, slot: saves.SaveSlot | None) -> None:
        self._loading = True
        try:
            self._scroll.clear()
            self._vars.clear()
            self._widgets.clear()
            d = self._resolve(slot)
            if d is None:
                ttk.Label(self._scroll.inner, text="(Not present in this slot.)", padding=20).pack()
                return
            entries = sorted(k for k, v in d.items() if isinstance(v, dict) and self._flag in v)
            if not entries:
                ttk.Label(self._scroll.inner, text="(Nothing to show here.)", padding=20).pack()
                return
            for r, key in enumerate(entries):
                var = tk.BooleanVar(value=bool(d[key].get(self._flag, False)))
                var.trace_add("write", lambda *_a, k=key: self._on_change(k))
                cb = ttk.Checkbutton(self._scroll.inner, text=key, variable=var)
                cb.grid(row=r, column=0, padx=10, pady=2, sticky="w")
                self._vars[key] = var
                self._widgets[key] = cb
        finally:
            self._loading = False

    def _resolve(self, slot: saves.SaveSlot | None) -> dict | None:
        if not slot:
            return None
        f = slot.get("user_progression.dat")
        if not f or f.doc is None:
            return None
        try:
            d: Any = f.doc["UserProgression"]
            for p in self._path:
                d = d[p]
            return d if isinstance(d, dict) else None
        except (KeyError, TypeError):
            return None

    def _on_change(self, key: str) -> None:
        if self._loading:
            return
        slot = self.app.current_slot
        d = self._resolve(slot)
        if d is None or key not in d:
            return
        new = bool(self._vars[key].get())
        if d[key].get(self._flag) == new:
            return
        d[key][self._flag] = new
        # Auto-clear the "new" badge when toggling state
        if "isVisited" in d[key]:
            d[key]["isVisited"] = True
        slot.get("user_progression.dat").dirty = True
        self.app.mark_dirty()

    def _apply_filter(self) -> None:
        needle = self._filter_var.get().lower().strip()
        for key, w in self._widgets.items():
            if not needle or needle in key.lower():
                w.grid()
            else:
                w.grid_remove()

    def _set_visible(self, value: bool) -> None:
        for key, w in self._widgets.items():
            if w.winfo_ismapped():
                self._vars[key].set(value)

    def unlock_all(self) -> None:
        """Unlock every entry — ignores the filter."""
        slot = self.app.current_slot
        d = self._resolve(slot)
        if d is None:
            return
        touched = 0
        for key, val in d.items():
            if isinstance(val, dict) and self._flag in val:
                if val.get(self._flag) is not True:
                    val[self._flag] = True
                    touched += 1
                if "isVisited" in val and val["isVisited"] is not True:
                    val["isVisited"] = True
        if touched:
            slot.get("user_progression.dat").dirty = True
            self.app.mark_dirty()


# --------------------------------------------------------------------------- #
# Bulk subtab (Outfits / Portraits)                                           #
# --------------------------------------------------------------------------- #
class _BulkSubTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: Any, title: str, kind: str) -> None:
        super().__init__(parent, padding=20)
        self.app = app
        self._title = title
        self._kind = kind
        self._summary_var = tk.StringVar(value="")
        self._build()

    def _build(self) -> None:
        _hint(self, self._title + " — nested structure, so individual editing is skipped. Use bulk.")
        ttk.Label(self, textvariable=self._summary_var).pack(anchor="w", pady=(0, 14))
        actions = ttk.Frame(self)
        actions.pack(anchor="w")
        ttk.Button(actions, text="Unlock all", style="Primary.TButton",
                   command=lambda: self._bulk(True)).pack(side="left")
        ttk.Button(actions, text="Lock all", command=lambda: self._bulk(False)).pack(side="left", padx=10)

    def load(self, slot: saves.SaveSlot | None) -> None:
        total = unlocked = 0
        for state, flag in self._iter_entries(slot):
            total += 1
            if state.get(flag):
                unlocked += 1
        if total == 0:
            self._summary_var.set("(Not present in this slot.)")
        else:
            self._summary_var.set(f"{unlocked} of {total} items unlocked.")

    def _iter_entries(self, slot: saves.SaveSlot | None):
        if not slot:
            return
        f = slot.get("user_progression.dat")
        if not f or f.doc is None:
            return
        try:
            if self._kind == "outfits":
                lst = f.doc["UserProgression"]["Outfits"]["outfitsProgressionJson"]["outfitsProgressionStates"]
                for entry in lst:
                    for char, variants in entry.items():
                        for variant, state in variants.items():
                            if isinstance(state, dict) and "isPurchased" in state:
                                yield state, "isPurchased"
            elif self._kind == "portraits":
                d = f.doc["UserProgression"]["Portraits"]["portraitsProgressionJson"]
                for char, char_data in d.items():
                    if not isinstance(char_data, dict):
                        continue
                    states = char_data.get("portraitsProgressionStates", {})
                    for portrait, state in states.items():
                        if isinstance(state, dict) and "isUnlocked" in state:
                            yield state, "isUnlocked"
        except (KeyError, TypeError):
            return

    def _bulk(self, value: bool) -> None:
        slot = self.app.current_slot
        touched = 0
        for state, flag in self._iter_entries(slot):
            if state.get(flag) != value:
                state[flag] = value
                touched += 1
            if value and "isVisited" in state and state["isVisited"] is not True:
                state["isVisited"] = True
        if touched:
            slot.get("user_progression.dat").dirty = True
            self.app.mark_dirty()
        self.load(slot)
        self.app.set_status(f"{self._title}: {'unlocked' if value else 'locked'} {touched} items.")

    def unlock_all(self) -> None:
        self._bulk(True)


# --------------------------------------------------------------------------- #
# Rewards tab                                                                 #
# --------------------------------------------------------------------------- #
class RewardsTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: Any) -> None:
        super().__init__(parent, padding=8)
        self.app = app
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True)
        self._main = _UnlockListSubTab(
            self._nb, app, "Main rewards (documents, extreme runs, progressive challenges)",
            path=("Rewards", "rewardsJson"), flag_key="isUnlocked",
        )
        self._community = _UnlockListSubTab(
            self._nb, app, "Community / Twitch / Redynx rewards",
            path=("Redynx", "redlynxProgressionJson"), flag_key="isGiven",
        )
        self._nb.add(self._main, text="Main rewards")
        self._nb.add(self._community, text="Community / Twitch")

    def load(self, slot: saves.SaveSlot | None) -> None:
        self._main.load(slot)
        self._community.load(slot)

    def unlock_all(self) -> None:
        self._main.unlock_all()
        self._community.unlock_all()


# --------------------------------------------------------------------------- #
# Cosmetics tab                                                               #
# --------------------------------------------------------------------------- #
class CosmeticsTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: Any) -> None:
        super().__init__(parent, padding=8)
        self.app = app
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True)
        self._frames = _UnlockListSubTab(
            self._nb, app, "Icon frames",
            path=("IconFrames", "iconFramesProgressionJson"), flag_key="isUnlocked",
        )
        self._accessories = _UnlockListSubTab(
            self._nb, app, "Accessories",
            path=("Accessories", "accessoriesProgressionJson"), flag_key="isPurchased",
        )
        self._outfits = _BulkSubTab(self._nb, app, "Outfits", kind="outfits")
        self._portraits = _BulkSubTab(self._nb, app, "Portraits", kind="portraits")
        self._nb.add(self._frames, text="Frames")
        self._nb.add(self._accessories, text="Accessories")
        self._nb.add(self._outfits, text="Outfits")
        self._nb.add(self._portraits, text="Portraits")

    def load(self, slot: saves.SaveSlot | None) -> None:
        self._frames.load(slot)
        self._accessories.load(slot)
        self._outfits.load(slot)
        self._portraits.load(slot)

    def unlock_all(self) -> None:
        self._frames.unlock_all()
        self._accessories.unlock_all()
        self._outfits.unlock_all()
        self._portraits.unlock_all()


# --------------------------------------------------------------------------- #
# Advanced tab                                                                #
# --------------------------------------------------------------------------- #
class AdvancedTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: Any) -> None:
        super().__init__(parent, padding=18)
        self.app = app
        self._current_file: saves.SaveFile | None = None
        self._build()

    def _build(self) -> None:
        _section_header(self, "Advanced — raw JSON")
        _hint(self, "Power-user view. Edit any save file's JSON directly. Click Apply to push "
                    "changes into memory; Save All at the bottom writes encrypted bytes to disk.")
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="File:").pack(side="left")
        self._file_var = tk.StringVar()
        self._file_combo = ttk.Combobox(top, textvariable=self._file_var, state="readonly", width=34)
        self._file_combo.pack(side="left", padx=8)
        self._file_combo.bind("<<ComboboxSelected>>", lambda _e: self._show_selected())

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self._text = tk.Text(body, wrap="none", font=("Consolas", 10), undo=True, maxundo=200,
                             background="#ffffff", foreground="#1d1d1f", insertbackground="#1d1d1f",
                             borderwidth=1, relief="solid")
        sv = ttk.Scrollbar(body, orient="vertical", command=self._text.yview)
        sh = ttk.Scrollbar(body, orient="horizontal", command=self._text.xview)
        self._text.configure(yscrollcommand=sv.set, xscrollcommand=sh.set)
        self._text.grid(row=0, column=0, sticky="nsew")
        sv.grid(row=0, column=1, sticky="ns")
        sh.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Apply edits to slot", style="Primary.TButton",
                   command=self._apply).pack(side="left")

    def load(self, slot: saves.SaveSlot | None) -> None:
        if not slot:
            self._file_combo.configure(values=[])
            self._file_var.set("")
            self._text.delete("1.0", "end")
            self._current_file = None
            return
        names = sorted(slot.files.keys())
        self._file_combo.configure(values=names)
        default = "user_progression.dat" if "user_progression.dat" in names else (names[0] if names else "")
        self._file_var.set(default)
        self._show_selected()

    def _show_selected(self) -> None:
        slot = self.app.current_slot
        if not slot:
            return
        f = slot.get(self._file_var.get())
        self._current_file = f
        self._text.delete("1.0", "end")
        if not f:
            return
        if f.doc is not None:
            self._text.insert("1.0", json.dumps(f.doc, indent=2, ensure_ascii=False))
        else:
            self._text.insert("1.0", f.plaintext.rstrip(b"\x00").decode("utf-8", errors="replace"))
        self._text.edit_modified(False)
        self._text.edit_reset()

    def _apply(self) -> None:
        if not self._current_file:
            return
        text = self._text.get("1.0", "end-1c")
        if self._current_file.doc is not None:
            try:
                self._current_file.doc = json.loads(text)
            except json.JSONDecodeError as e:
                messagebox.showerror("WWZ Save Editor", f"JSON is invalid:\n\n{e}")
                return
        else:
            self._current_file.plaintext = text.encode("utf-8") + (
                b"\x00" if self._current_file.had_trailing_null else b""
            )
        self._current_file.dirty = True
        self.app.mark_dirty()
        self.app.refresh_other_tabs(self)
        self.app.set_status(f"Applied edits to {self._current_file.name}.")
