"""Download backends behind one interface.

SpotiFLAC (lossless) is primary for FLAC; spotdl is the fallback and the direct
path for lossy formats. Both are external CLIs invoked via subprocess — spotdl
pins an old FastAPI and SpotiFLAC has non-standard packaging, so neither is a
library dependency. A backend that isn't installed raises BackendUnavailable and
the orchestrator falls through to the next one.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..config import Settings
from .base import DownloadBackend, Track
from .tags import track_from_file

AUDIO_SUFFIXES = {".flac", ".mp3", ".m4a", ".opus", ".ogg", ".wav"}


class BackendUnavailable(RuntimeError):
    """Raised when a backend's CLI isn't installed or fails to run."""


def audio_files(directory: Path) -> set[Path]:
    if not directory.exists():
        return set()
    return {p for p in directory.rglob("*") if p.suffix.lower() in AUDIO_SUFFIXES}


def build_spotdl_command(playlist_url: str, out_dir: Path, audio_format: str) -> list[str]:
    return [
        "spotdl",
        "download",
        playlist_url,
        "--output",
        str(out_dir),
        "--format",
        audio_format,
    ]


def build_spotiflac_command(playlist_url: str, out_dir: Path) -> list[str]:
    # Override point for the user's environment (SpotiFLAC packaging varies).
    # CRATEMIND_SPOTIFLAC_CMD may name a different executable or wrapper.
    exe = os.environ.get("CRATEMIND_SPOTIFLAC_CMD", "spotiflac")
    return [exe, playlist_url, "--output", str(out_dir)]


def _run(command: list[str]) -> None:
    if shutil.which(command[0]) is None:
        raise BackendUnavailable(f"{command[0]!r} is not installed")
    try:
        _ = subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - passthrough
        raise BackendUnavailable(f"{command[0]} failed (exit {exc.returncode})") from exc


class SpotiFlacBackend:
    name: str = "spotiflac"

    def supports(self, audio_format: str) -> bool:
        return audio_format == "flac"

    def fetch(self, playlist_url: str, out_dir: Path) -> list[Track]:
        out_dir.mkdir(parents=True, exist_ok=True)
        before = audio_files(out_dir)
        _run(build_spotiflac_command(playlist_url, out_dir))
        fresh = audio_files(out_dir) - before
        return [track_from_file(p, source=self.name) for p in sorted(fresh)]


class SpotdlBackend:
    name: str = "spotdl"

    def __init__(self, audio_format: str) -> None:
        self.audio_format: str = audio_format

    def supports(self, audio_format: str) -> bool:
        return audio_format in ("flac", "mp3", "m4a")

    def fetch(self, playlist_url: str, out_dir: Path) -> list[Track]:
        out_dir.mkdir(parents=True, exist_ok=True)
        before = audio_files(out_dir)
        _run(build_spotdl_command(playlist_url, out_dir, self.audio_format))
        fresh = audio_files(out_dir) - before
        return [track_from_file(p, source=self.name) for p in sorted(fresh)]


def select_backends(audio_format: str) -> list[DownloadBackend]:
    """Ordered backends to try: lossless first for FLAC, spotdl as the net."""
    spotdl = SpotdlBackend(audio_format)
    if audio_format == "flac":
        return [SpotiFlacBackend(), spotdl]
    return [spotdl]


def fetch_playlist(playlist_url: str, settings: Settings) -> tuple[str, list[Track]]:
    """Try each backend in order; return (backend_name, tracks) from the first
    that's available and succeeds. Raises BackendUnavailable if none work.
    """
    last_error: BackendUnavailable | None = None
    for backend in select_backends(settings.audio_format):
        try:
            tracks = backend.fetch(playlist_url, settings.output_dir)
            return backend.name, tracks
        except BackendUnavailable as error:
            last_error = error
    raise BackendUnavailable(f"no usable download backend: {last_error}")
