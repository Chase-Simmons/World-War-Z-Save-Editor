"""Metadata about the WWZ class roster.

The order is the index used inside
`UserProgression.PVE.perksProgressionJson.data[i]` in the decoded save.
"""
from __future__ import annotations

CLASS_NAMES: list[str] = [
    "Gunslinger",
    "Hellraiser",
    "Medic",
    "Fixer",
    "Slasher",
    "Exterminator",
    "Vanguard",
    "Dronemaster",
]

MAX_LEVEL = 30
MIN_LEVEL = 1
# In-game prestige cap is 10. Stored value is offset by -1 (file -1..9 → game 0..10).
MAX_PRESTIGE = 9
MIN_PRESTIGE = -1  # -1 == never prestiged
