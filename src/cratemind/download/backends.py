"""Download backends behind one interface.

SpotiFLAC (lossless) is primary for FLAC; spotdl is the fallback and the direct
path for lossy formats. Both are external CLIs invoked via subprocess — spotdl
pins an old FastAPI and SpotiFLAC has non-standard packaging, so neither is a
library dependency. A backend that isn't installed raises BackendUnavailable and
the orchestrator falls through to the next one.
"""

from __future__ import annotations

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
    """Every audio file under ``directory`` (recursive) — used for the download count."""
    if not directory.exists():
        return set()
    return {p for p in directory.rglob("*") if p.suffix.lower() in AUDIO_SUFFIXES}


def staging_files(directory: Path) -> set[Path]:
    """Unsorted downloads in the output root (non-recursive); sorted files live in subfolders."""
    if not directory.exists():
        return set()
    return {p for p in directory.glob("*") if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES}


def build_spotdl_command(playlist_url: str, out_dir: Path, audio_format: str) -> list[str]:
    # spotdl's --output is a filename TEMPLATE, not a directory, so include a name
    # pattern to make files land inside out_dir with sensible names.
    output_template = f"{out_dir}/{{artists}} - {{title}}.{{output-ext}}"
    return [
        "spotdl",
        "download",
        playlist_url,
        "--output",
        output_template,
        "--format",
        audio_format,
        "--overwrite",
        "skip",
        "--scan-for-songs",
    ]


def build_spotiflac_command(playlist_url: str, out_dir: Path) -> list[str]:
    # SpotiFLAC CLI is positional: `spotiflac <url> <output_dir>`.
    return ["spotiflac", playlist_url, str(out_dir)]


def _run(command: list[str]) -> None:
    if shutil.which(command[0]) is None:
        raise BackendUnavailable(f"{command[0]!r} is not installed")
    # Inherit the terminal so the user sees live download progress (a playlist
    # download is one long subprocess; capturing output would hide all of it).
    try:
        _ = subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - passthrough
        raise BackendUnavailable(
            f"{command[0]} failed (exit {exc.returncode}); see the terminal for details"
        ) from exc


class SpotiFlacBackend:
    name: str = "spotiflac"

    def supports(self, audio_format: str) -> bool:
        return audio_format == "flac"

    def fetch(self, playlist_url: str, out_dir: Path) -> list[Track]:
        return _run_and_collect(build_spotiflac_command(playlist_url, out_dir), out_dir, self.name)


class SpotdlBackend:
    name: str = "spotdl"

    def __init__(self, audio_format: str) -> None:
        self.audio_format: str = audio_format

    def supports(self, audio_format: str) -> bool:
        return audio_format in ("flac", "mp3", "m4a")

    def fetch(self, playlist_url: str, out_dir: Path) -> list[Track]:
        command = build_spotdl_command(playlist_url, out_dir, self.audio_format)
        return _run_and_collect(command, out_dir, self.name)


def _run_and_collect(command: list[str], out_dir: Path, source: str) -> list[Track]:
    """Run a downloader, then return the unsorted files it left in the root.

    A mid-download crash can still leave usable files; process those rather than
    orphan them. Only re-raise when nothing landed (e.g. the CLI isn't installed).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        _run(command)
    except BackendUnavailable:
        if not staging_files(out_dir):
            raise
    return [track_from_file(p, source=source) for p in sorted(staging_files(out_dir))]


def select_backends(audio_format: str) -> list[DownloadBackend]:
    """Backends to try, in order.

    SpotiFLAC (true lossless) is paused: its free, no-account providers are
    reverse-engineered mirrors that are down most of the time, which would make
    a FLAC run hang for minutes before failing. spotdl is the dependable default.
    To re-enable lossless once it's stable, prepend ``SpotiFlacBackend()`` for the
    flac case — ``fetch_playlist`` already falls through to spotdl if it gets
    nothing.
    """
    return [SpotdlBackend(audio_format)]


def fetch_playlist(playlist_url: str, settings: Settings) -> tuple[str, list[Track]]:
    """Download the playlist with the first available backend.

    Returns ``(name, tracks)``; ``(name, [])`` when a backend ran but found
    nothing new (a rerun). Raises BackendUnavailable only when nothing is
    installed, so the caller can tell "no new tracks" from "no downloader".
    """
    if "open.spotify.com" not in playlist_url and not playlist_url.startswith("spotify:"):
        raise BackendUnavailable("not a Spotify playlist URL")
    ran_name: str | None = None
    install_error: BackendUnavailable | None = None
    for backend in select_backends(settings.audio_format):
        try:
            tracks = backend.fetch(playlist_url, settings.output_dir)
        except BackendUnavailable as error:
            install_error = error  # this backend's CLI isn't installed or failed
            continue
        ran_name = backend.name
        if tracks:
            return backend.name, tracks
    if ran_name is None:
        # Every backend was unavailable — nothing is installed to download with.
        raise BackendUnavailable(f"no download backend available: {install_error}")
    # A backend ran but produced no new files; the caller checks the store to
    # decide whether that's a real failure or just a rerun with nothing to do.
    return ran_name, []
