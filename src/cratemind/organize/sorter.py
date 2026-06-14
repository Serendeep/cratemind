"""Move an analyzed track into its destination folder.

The destination comes from the user's template rendered with the resolved genre
and BPM bucket. Files are moved (not copied); name collisions get a numeric
suffix so two tracks never clobber each other.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from ..config import Settings
from ..download.base import Track
from ..genre.resolve import ArtistGenreLookup, resolve_genre
from .template import UNSORTED, render_path


def _link_or_copy(src: Path, dest: Path) -> None:
    """Hardlink the cached original into the sorted tree, keeping the cache so
    reruns can skip the download. Falls back to a copy across filesystems."""
    try:
        os.link(src, dest)
    except OSError:
        _ = shutil.copy2(src, dest)


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
    artist_genre_lookup: ArtistGenreLookup | None = None,
) -> Track:
    if track.file_path is None:
        return track.update(status="failed")
    genre = resolve_genre(track, artist_genre_lookup=artist_genre_lookup)
    folder = destination_dir(track, settings, genre)
    # Defense in depth: a template/genre must never escape the output root.
    root = settings.output_dir.resolve()
    if not folder.resolve().is_relative_to(root):
        folder = root / UNSORTED
    folder.mkdir(parents=True, exist_ok=True)
    dest = unique_path(folder / track.file_path.name)
    _link_or_copy(track.file_path, dest)
    return track.update(genre=genre, file_path=dest, status="sorted")
