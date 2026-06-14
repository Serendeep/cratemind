"""Normalize genre names so cross-source variants land in one folder.

MusicBrainz says "Drum & Bass", Spotify says "drum and bass" — without
canonicalization those are two folders. We lowercase, expand `&`, collapse
whitespace, and apply an alias map.
"""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")

DEFAULT_ALIASES: dict[str, str] = {
    "dnb": "drum and bass",
    "d n b": "drum and bass",
    "hiphop": "hip hop",
    "rnb": "r and b",
    "edm": "electronic",
}


def canonicalize(name: str | None, aliases: dict[str, str] | None = None) -> str | None:
    """Return a normalized genre, or None if there's nothing usable."""
    if name is None:
        return None
    text = name.strip().lower().replace("&", " and ")
    text = _WHITESPACE.sub(" ", text).strip()
    if not text:
        return None
    table = DEFAULT_ALIASES if aliases is None else {**DEFAULT_ALIASES, **aliases}
    return table.get(text, text)
