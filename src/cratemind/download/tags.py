"""Read embedded tags from a downloaded file and turn them into a Track.

Genre and title/artist come from whatever the downloader embedded (MusicBrainz
via SpotiFLAC, Spotify via spotdl). We never trust the audio for tempo — BPM is
computed later — so this layer only reads metadata.
"""

from __future__ import annotations

import hashlib
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
