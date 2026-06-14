"""Track model + the download-backend contract.

A `DownloadBackend` turns a Spotify playlist URL into local audio files plus a
Track per item. SpotiFLAC (lossless) is primary; spotdl is the fallback and the
direct path for lossy formats. Both implement this Protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol, runtime_checkable

TrackStatus = str  # queued | downloading | analyzing | sorted | failed


@dataclass(frozen=True)
class Track:
    spotify_id: str
    title: str
    artist: str
    genre: str | None = None
    bpm: int | None = None
    bpm_bucket: str | None = None
    key: str | None = None  # Camelot code, e.g. "8A"
    source: str | None = None  # "spotiflac" | "spotdl"
    lossless: bool = False
    file_path: Path | None = None
    status: TrackStatus = "queued"

    def update(self, **changes: object) -> "Track":
        return replace(self, **changes)


@runtime_checkable
class DownloadBackend(Protocol):
    name: str

    def supports(self, audio_format: str) -> bool:
        """Whether this backend can serve the requested format."""
        ...

    def fetch(self, playlist_url: str, out_dir: Path) -> list[Track]:
        """Download every track in the playlist into out_dir, return Tracks."""
        ...
