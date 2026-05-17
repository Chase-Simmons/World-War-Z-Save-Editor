"""Model layer: discover save slots, decrypt files, hold edits, write them back."""
from __future__ import annotations

import datetime
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import crypto


@dataclass
class SaveFile:
    """One decrypted .dat file inside a slot."""

    path: Path
    plaintext: bytes
    doc: dict | list | None        # parsed JSON document, or None if file isn't JSON
    had_trailing_null: bool
    dirty: bool = False

    @property
    def name(self) -> str:
        return self.path.name

    def serialize(self) -> bytes:
        """Turn current state back into encrypted bytes ready to write."""
        if self.doc is not None:
            body = json.dumps(self.doc, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        else:
            body = self.plaintext.rstrip(b"\x00")
        if self.had_trailing_null:
            body += b"\x00"
        return crypto.encrypt(body, self.path.name)


@dataclass
class SaveSlot:
    """One save slot: a directory containing a user_progression.dat and friends."""

    folder: Path
    files: dict[str, SaveFile] = field(default_factory=dict)

    @property
    def label(self) -> str:
        """Friendly name for the slot picker."""
        try:
            mtime = max(f.path.stat().st_mtime for f in self.files.values() if f.path.exists())
            stamp = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        except (OSError, ValueError):
            stamp = "?"
        return f"{self.folder.name}    (last modified {stamp})"

    @property
    def dirty(self) -> bool:
        return any(f.dirty for f in self.files.values())

    def get(self, name: str) -> SaveFile | None:
        return self.files.get(name)


def _try_decrypt(path: Path) -> SaveFile | None:
    try:
        plain = crypto.decrypt(path.read_bytes(), path.name)
    except Exception:
        return None
    had_null = plain.endswith(b"\x00")
    body = plain.rstrip(b"\x00")
    doc: dict | list | None
    try:
        doc = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        doc = None
    return SaveFile(path=path, plaintext=plain, doc=doc, had_trailing_null=had_null)


def discover_slots(root: Path) -> list[SaveSlot]:
    """Find every directory under `root` that contains a user_progression.dat
    and load all sibling *.dat files as one slot.
    """
    if not root.exists():
        return []
    progression_files = list(root.rglob("user_progression.dat"))
    # Filter out backups
    progression_files = [p for p in progression_files if ".bak_" not in p.name]

    slots: list[SaveSlot] = []
    for prog in progression_files:
        slot_dir = prog.parent
        files: dict[str, SaveFile] = {}
        for dat in slot_dir.glob("*.dat"):
            if ".bak_" in dat.name:
                continue
            sf = _try_decrypt(dat)
            if sf is not None:
                files[dat.name] = sf
        if files:
            slots.append(SaveSlot(folder=slot_dir, files=files))

    # Most-recent first
    def slot_mtime(slot: SaveSlot) -> float:
        try:
            return max(f.path.stat().st_mtime for f in slot.files.values())
        except (OSError, ValueError):
            return 0.0

    slots.sort(key=slot_mtime, reverse=True)
    return slots


def save_slot(slot: SaveSlot) -> list[Path]:
    """Write back every dirty file in the slot, backing each up first.
    Returns the list of files written.
    """
    written: list[Path] = []
    for f in slot.files.values():
        if not f.dirty:
            continue
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = f.path.with_name(f.path.name + f".bak_{ts}")
        shutil.copy2(f.path, backup)
        f.path.write_bytes(f.serialize())
        f.dirty = False
        # refresh the cached plaintext to match what's now on disk
        try:
            f.plaintext = crypto.decrypt(f.path.read_bytes(), f.path.name)
        except Exception:
            pass
        written.append(f.path)
    return written


def list_backups(file_path: Path) -> list[Path]:
    return sorted(
        file_path.parent.glob(file_path.name + ".bak_*"), reverse=True
    )
