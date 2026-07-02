"""Read embedded tags from a downloaded file and turn them into a Track.

Genre and title/artist come from whatever the downloader embedded (MusicBrainz
via SpotiFLAC, Spotify via spotdl). We never trust the audio for tempo — BPM is
computed later — so this layer only reads metadata.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import mutagen

from ..genre.canonical import canonicalize
from .base import Track

LOSSLESS_SUFFIXES = {".flac", ".wav", ".aiff", ".aif", ".alac"}


def is_lossless(path: Path) -> bool:
    return Path(path).suffix.lower() in LOSSLESS_SUFFIXES


def stable_id(artist: str, title: str) -> str:
    """Deterministic id for a track when no Spotify id is embedded.

    Keyed on artist+title so the same track resolves to the same id across
    runs — that's what makes resume and manifest matching work.
    """
    digest = hashlib.sha1(f"{artist}\x00{title}".encode()).hexdigest()
    return digest[:16]


def read_tags(path: Path) -> dict[str, str | None]:
    audio = mutagen.File(str(path), easy=True)
    if not audio:
        return {}

    def first(key: str) -> str | None:
        value = audio.get(key)
        return value[0] if value else None

    return {
        "title": first("title"),
        "artist": first("artist"),
        "genre": first("genre"),
        "date": first("date"),
    }


def read_art(path: Path) -> tuple[bytes, str] | None:
    """Embedded cover art as (bytes, mime), or None. Best-effort — art is a
    nicety, so any parse problem means "no art", never an error."""
    try:
        audio = mutagen.File(str(path))
        if audio is None:
            return None
        tags = audio.tags
        if tags is not None and hasattr(tags, "getall"):  # ID3 (mp3, some wav/aiff)
            pics = tags.getall("APIC")
            if pics:
                return bytes(pics[0].data), pics[0].mime or "image/jpeg"
        pictures = getattr(audio, "pictures", None)  # FLAC picture blocks
        if pictures:
            return bytes(pictures[0].data), pictures[0].mime or "image/jpeg"
        if tags is not None:  # MP4 covr atoms
            covers = tags.get("covr")
            if covers:
                from mutagen.mp4 import MP4Cover

                mime = "image/png" if covers[0].imageformat == MP4Cover.FORMAT_PNG else "image/jpeg"
                return bytes(covers[0]), mime
    except Exception:
        return None
    return None


@lru_cache(maxsize=1024)
def _has_art_cached(path_str: str, _mtime_ns: int) -> bool:
    return read_art(Path(path_str)) is not None


def has_art(path: Path) -> bool:
    """Presence-only, mtime-keyed cache. Caching booleans instead of the art
    bytes keeps a long-lived local server from pinning megabytes of covers;
    the art route re-reads on demand and the browser caches the response."""
    try:
        return _has_art_cached(str(path), path.stat().st_mtime_ns)
    except OSError:
        return False


def track_from_file(path: Path, *, source: str) -> Track:
    tags = read_tags(path)
    title = tags.get("title") or path.stem
    artist = tags.get("artist") or "unknown"
    return Track(
        spotify_id=stable_id(artist, title),
        title=title,
        artist=artist,
        genre=canonicalize(tags.get("genre")),
        source=source,
        # Only SpotiFLAC delivers true lossless. A spotdl ".flac" is a lossy
        # YouTube source in a lossless container, so it doesn't count.
        lossless=is_lossless(path) and source == "spotiflac",
        file_path=Path(path),
        status="downloading",
    )
