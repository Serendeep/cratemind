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
    if not directory.exists():
        return set()
    return {p for p in directory.rglob("*") if p.suffix.lower() in AUDIO_SUFFIXES}


def cache_dir(out_dir: Path) -> Path:
    """Persistent download cache. Keeping originals here lets the downloaders
    skip what they've already fetched, so reruns don't re-download.

    The name has no leading dot on purpose: spotdl strips a leading dot from
    output-path segments, which would make it write to a different folder than
    cratemind watches.
    """
    return out_dir / "cratemind-cache"


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
        cache = cache_dir(out_dir)
        cache.mkdir(parents=True, exist_ok=True)
        before = audio_files(cache)
        _run(build_spotiflac_command(playlist_url, cache))
        after = audio_files(cache)
        # Newly downloaded files; if nothing's new, everything was already cached
        # (a rerun), so process what's there.
        produced = (after - before) or after
        return [track_from_file(p, source=self.name) for p in sorted(produced)]


class SpotdlBackend:
    name: str = "spotdl"

    def __init__(self, audio_format: str) -> None:
        self.audio_format: str = audio_format

    def supports(self, audio_format: str) -> bool:
        return audio_format in ("flac", "mp3", "m4a")

    def fetch(self, playlist_url: str, out_dir: Path) -> list[Track]:
        cache = cache_dir(out_dir)
        cache.mkdir(parents=True, exist_ok=True)
        before = audio_files(cache)
        _run(build_spotdl_command(playlist_url, cache, self.audio_format))
        after = audio_files(cache)
        # Newly downloaded files; if nothing's new, everything was already cached
        # (a rerun), so process what's there.
        produced = (after - before) or after
        return [track_from_file(p, source=self.name) for p in sorted(produced)]


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
    """Try each backend in order; return (backend_name, tracks) from the first
    that's available and succeeds. Raises BackendUnavailable if none work.
    """
    if "open.spotify.com" not in playlist_url and not playlist_url.startswith("spotify:"):
        raise BackendUnavailable("not a Spotify playlist URL")
    last_error: BackendUnavailable | None = None
    for backend in select_backends(settings.audio_format):
        try:
            tracks = backend.fetch(playlist_url, settings.output_dir)
        except BackendUnavailable as error:
            last_error = error
            continue
        if tracks:
            return backend.name, tracks
        # A backend that runs but downloads nothing (e.g. its providers are down)
        # shouldn't strand the run — fall through to the next one.
        last_error = BackendUnavailable(f"{backend.name} downloaded nothing")
    raise BackendUnavailable(f"no usable download backend: {last_error}")
