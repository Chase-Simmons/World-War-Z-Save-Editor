# WWZ Save Editor

A small open-source GUI for editing **World War Z** save data (Saber/Focus,
PlatformStorage `.dat` files).

Point it at your save folder once and the tool auto-discovers every save slot
underneath. Each slot is grouped into clean, purpose-built tabs — you don't
deal with file paths or raw JSON unless you want to.

Zero external dependencies — pure Python standard library.

## Features

- **Auto-discovers save slots** under the chosen folder. On Windows it
  guesses `%LOCALAPPDATA%\Saber\WWZ\client\storage` if it exists.
- **Per-domain tabs:**
  - **Classes** — level (read-only, recomputed by the game), prestige,
    experience for each of the 8 classes; active class picker.
  - **Currency** — premium currency, coins, account level, episodes owned,
    selected icon frame.
  - **Weapons** — level + XP for every firearm in the revamped progression
    system (level cap 15), with a filter and bulk "Max" / "Reset XP" actions.
  - **Rewards** — main rewards (campaign documents, extreme runs, progressive
    challenges) plus the Community/Twitch/Redynx rewards. Each can be toggled
    individually or unlocked in bulk.
  - **Cosmetics** — sub-tabbed into Frames, Accessories, Outfits, and
    Portraits with the same individual / bulk pattern.
  - **Advanced** — raw JSON view for any file in the slot, for anything the
    purpose-built tabs don't cover.
- **"Unlock & Max All"** — one-click to apply max XP + max prestige + every
  unlock + currency boost across the slot.
- **"Clear badges"** — sets every `isVisited` flag to `true` (removes the red
  "new!" dots in the game UI).
- **Automatic timestamped backups** before every save (`*.dat.bak_<timestamp>`)
  and a Backups dialog that lists and restores any backup the tool has made.
- **Per-monitor DPI awareness** on Windows so widgets render at the right
  size on high-DPI displays.
- **Save All** is greyed out unless something in the slot has changed; JSON
  is validated before being written. **Ctrl+S** saves.

## Install / run

Requires Python 3.10 or newer (tkinter ships with the standard Windows
installer).

```bash
git clone https://github.com/Chase-Simmons/World-War-Z-Save-Editor
cd World-War-Z-Save-Editor
python -m wwz_save_editor
```

Optionally `pip install .` to register a `wwz-save-editor` console script.

## How the save format works

The reverse-engineered details live in
[`wwz_save_editor/crypto.py`](wwz_save_editor/crypto.py). In short:

- On-disk file = `[XOR-obfuscated 4-byte zlib header][rest of the zlib stream]`
- The XOR key is derived from the filename and two compile-time constants in
  the executable's `.rdata`. One of the constants is the bit pattern of
  `float(π)` reinterpreted as int.
- Past the first 4 bytes, the data is a stock `deflate` stream that inflates
  to JSON (compact, optional trailing NUL byte).

So the "encryption" really only obfuscates the zlib magic header. The editor
reproduces the same XOR + deflate pipeline so the game accepts our output.

## Notes on what will and won't stick

- **Class levels are server-recomputed from XP.** The level field can't be
  set directly. You bump Experience; on your next match the game adds one
  level (one level per match) and resets XP. **Prestige is independent** and
  takes effect immediately.
- **Weapon levels are directly settable.**
- **Cosmetics, frames, accessories, rewards, currency** generally stick on
  reload.
- WWZ has cloud progression for some fields. If the game is launched online,
  the server can override local edits to values it considers authoritative.
  Play offline if you want a particular edit to take effect untouched.

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

Use on your own save data only. Modifying save data may violate a game's
terms of service. The authors aren't responsible for lost progression, banned
accounts, or anything else that happens because you ran an unofficial tool
against an unofficial save format.
