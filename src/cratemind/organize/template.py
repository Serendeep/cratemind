"""Render a destination path from a user folder template.

Tokens: {genre} {bpm_bucket} {bpm} {artist} {year}. Each template segment is
substituted then sanitized, so a genre containing a slash can't inject extra
path levels. Missing genre/bucket fall back to `unsorted` — never strand a file.
"""

from __future__ import annotations

import re
from pathlib import Path

UNSORTED = "unsorted"
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TOKEN = re.compile(r"\{(\w+)\}")
_WHITESPACE = re.compile(r"\s+")


def sanitize(component: str) -> str:
    """Make a single path component safe; empty results fall back to `unsorted`."""
    cleaned = _ILLEGAL.sub("_", component)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip().strip(".")
    return cleaned or UNSORTED


def render_path(
    template: str,
    *,
    genre: str | None,
    bpm: int | None,
    bpm_bucket: str | None,
    artist: str | None,
    year: int | None,
) -> Path:
    values = {
        "genre": genre or UNSORTED,
        "bpm": "" if bpm is None else str(bpm),
        "bpm_bucket": bpm_bucket or UNSORTED,
        "artist": artist or "unknown",
        "year": "" if year is None else str(year),
    }

    def substitute(match: re.Match[str]) -> str:
        return values.get(match.group(1), match.group(0))

    parts: list[str] = []
    for segment in template.split("/"):
        if not segment:
            continue
        parts.append(sanitize(_TOKEN.sub(substitute, segment)))
    return Path(*parts) if parts else Path(UNSORTED)
