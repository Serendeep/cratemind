"""Coarse genre from Deezer's public API — the no-auth fallback below the audio model.

Deezer's genres are coarse (techno collapses to "Electro"/"Dance"), so this only
keeps a track out of the artist bucket. Failures return None; the HTTP fetch is
injected so tests don't hit the network.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

JsonFetcher = Callable[[str], dict[str, Any]]

_SEARCH = "https://api.deezer.com/search"
_ALBUM = "https://api.deezer.com/album"

# Deezer's coarse genre names → clean folder labels. Unknown names pass through
# lowercased (canonicalize normalizes them); "electro" is a false friend folded
# to the generic bucket on purpose.
_COARSE: dict[str, str] = {
    "electro": "electronic",
    "dance": "electronic",
    "dance/electro pop": "electronic",
    "techno/house": "electronic",
    "trance": "trance",
    "house": "house",
    "techno": "techno",
    "drum & bass": "drum and bass",
    "dubstep": "dubstep",
}


def _default_fetch_json(url: str) -> dict[str, Any]:
    import httpx

    response = httpx.get(url, timeout=8.0)
    _ = response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def _coarse_label(name: str | None) -> str | None:
    if not name:
        return None
    key = name.strip().lower()
    return _COARSE.get(key, key) or None


def lookup_deezer_genre(
    artist: str,
    title: str,
    *,
    fetch_json: JsonFetcher = _default_fetch_json,
) -> str | None:
    """Best-effort coarse genre for (artist, title), or None.

    Resolves the track → its album → the album's first genre, then folds that to
    a clean coarse label. Any miss or error returns None.
    """
    query = urlencode({"q": f'artist:"{artist}" track:"{title}"'})
    try:
        results = fetch_json(f"{_SEARCH}?{query}")
        hits = results.get("data") or []
        if not hits:
            return None
        album_id = (hits[0].get("album") or {}).get("id")
        if not album_id:
            return None
        album = fetch_json(f"{_ALBUM}/{album_id}")
        genres = (album.get("genres") or {}).get("data") or []
        raw = genres[0].get("name") if genres else None
    except Exception:
        return None
    return _coarse_label(raw)
