"""Move an analyzed track from the download root into its destination folder.

The folder comes from the template rendered with the resolved genre and BPM
bucket. The file is moved (not copied); name collisions get a numeric suffix.
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

from ..config import Settings
from ..download.base import Track
from ..genre.resolve import (
    ArtistGenreLookup,
    AudioGenreLookup,
    CoarseGenreLookup,
    resolve_genre,
)
from .template import UNSORTED, render_path

# Serializes name-reservation + move so concurrent job threads writing to the
# same output dir can't pick the same destination and clobber each other's file.
_PLACE_LOCK = threading.Lock()


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def destination_dir(track: Track, settings: Settings, genre: str | None) -> Path:
    relative = render_path(
        settings.folder_template,
        genre=genre,
        bpm=track.bpm,
        bpm_bucket=track.bpm_bucket,
        key=track.key,
        artist=track.artist,
        year=None,
    )
    return settings.output_dir / relative


def sort_track(
    track: Track,
    settings: Settings,
    *,
    audio_genre_lookup: AudioGenreLookup | None = None,
    coarse_genre_lookup: CoarseGenreLookup | None = None,
    artist_genre_lookup: ArtistGenreLookup | None = None,
) -> Track:
    if track.file_path is None:
        return track.update(status="failed")
    genre = resolve_genre(
        track,
        audio_genre_lookup=audio_genre_lookup,
        coarse_genre_lookup=coarse_genre_lookup,
        artist_genre_lookup=artist_genre_lookup,
    )
    folder = destination_dir(track, settings, genre)
    # Defense in depth: a template/genre must never escape the output root.
    root = settings.output_dir.resolve()
    if not folder.resolve().is_relative_to(root):
        folder = root / UNSORTED
    folder.mkdir(parents=True, exist_ok=True)
    with _PLACE_LOCK:
        dest = unique_path(folder / track.file_path.name)
        _ = shutil.move(str(track.file_path), str(dest))
    return track.update(genre=genre, file_path=dest, status="sorted")
