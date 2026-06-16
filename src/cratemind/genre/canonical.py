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


def normalize_genre(name: str) -> str:
    """Lowercase, expand `&`, and collapse whitespace — the form aliases key on.

    Used both before alias lookup and when storing an alias, so a saved alias key
    matches what `canonicalize` looks up.
    """
    text = name.strip().lower().replace("&", " and ")
    return _WHITESPACE.sub(" ", text).strip()


def canonicalize(name: str | None, aliases: dict[str, str] | None = None) -> str | None:
    """Return a normalized genre, or None if there's nothing usable."""
    if name is None:
        return None
    text = normalize_genre(name)
    if not text:
        return None
    table = DEFAULT_ALIASES if aliases is None else {**DEFAULT_ALIASES, **aliases}
    return table.get(text, text)
