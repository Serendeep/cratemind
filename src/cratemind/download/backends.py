"""Download backends behind one interface.

SpotiFLAC (lossless) is primary for FLAC; spotdl is the fallback and the direct
path for lossy formats. Both are external CLIs invoked via subprocess — spotdl
pins an old FastAPI and SpotiFLAC has non-standard packaging, so neither is a
library dependency. A backend that isn't installed raises BackendUnavailable and
the orchestrator falls through to the next one.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..config import Settings
from .base import DownloadBackend, Track
from .tags import stable_id, track_from_file

AUDIO_SUFFIXES = {".flac", ".mp3", ".m4a", ".opus", ".ogg", ".wav"}
TRACKLIST_FILE = ".cratemind-tracklist.spotdl"


def normalize_title(title: str | None) -> str:
    """Lowercase + collapse whitespace, for matching tracks across sources."""
    return " ".join((title or "").lower().split())


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
        self.playlist_name: str | None = None  # captured from the tracklist save-file

    def supports(self, audio_format: str) -> bool:
        return audio_format in ("flac", "mp3", "m4a")

    def fetch(self, playlist_url: str, out_dir: Path) -> list[Track]:
        # Capture the playlist's full tracklist first (metadata only, no download)
        # so we can tell which songs spotdl couldn't fetch and report them.
        save_file = out_dir / TRACKLIST_FILE
        _save_tracklist(playlist_url, save_file)
        command = build_spotdl_command(playlist_url, out_dir, self.audio_format)
        downloaded = _run_and_collect(command, out_dir, self.name)
        self.playlist_name = _playlist_name(save_file)
        failed = _failed_from_expected(save_file, downloaded, self.name)
        save_file.unlink(missing_ok=True)
        return downloaded + failed


def _playlist_name(save_file: Path) -> str | None:
    """The playlist's display name from a spotdl save-file, if available."""
    if not save_file.exists():
        return None
    try:
        songs = json.loads(save_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return (songs[0].get("list_name") if songs else None) or None


def _save_tracklist(playlist_url: str, save_file: Path) -> None:
    """Write the playlist's resolved tracklist to ``save_file`` (best effort)."""
    save_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        _run(["spotdl", "save", playlist_url, "--save-file", str(save_file)])
    except BackendUnavailable:
        pass  # no tracklist → failed downloads just won't be surfaced this run


def _expected_tracks(save_file: Path, source: str) -> list[Track]:
    """Parse a spotdl save-file into Track stubs marked failed (no file yet)."""
    if not save_file.exists():
        return []
    try:
        songs = json.loads(save_file.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    tracks: list[Track] = []
    for song in songs:
        name = song.get("name")
        artist = song.get("artist") or next(iter(song.get("artists") or []), None)
        if not name or not artist:
            continue
        tracks.append(
            Track(
                spotify_id=stable_id(artist, name),
                title=name,
                artist=artist,
                source=source,
                status="failed",
                file_path=None,
            )
        )
    return tracks


def _failed_from_expected(save_file: Path, downloaded: list[Track], source: str) -> list[Track]:
    """Expected songs that have no matching downloaded file, as failed Tracks."""
    expected = _expected_tracks(save_file, source)
    if not expected:
        return []
    got = {normalize_title(t.title) for t in downloaded}
    return [e for e in expected if normalize_title(e.title) not in got]


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


def fetch_playlist(
    playlist_url: str, settings: Settings
) -> tuple[str, list[Track], str | None]:
    """Download the playlist with the first available backend.

    Returns ``(backend, tracks, playlist_name)``; an empty track list when a
    backend ran but found nothing new (a rerun). Raises BackendUnavailable only
    when nothing is installed, so the caller can tell "no new tracks" from "no
    downloader". The playlist name is best-effort (None when unknown).
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
            return backend.name, tracks, getattr(backend, "playlist_name", None)
    if ran_name is None:
        # Every backend was unavailable — nothing is installed to download with.
        raise BackendUnavailable(f"no download backend available: {install_error}")
    # A backend ran but produced no new files; the caller checks the store to
    # decide whether that's a real failure or just a rerun with nothing to do.
    return ran_name, [], None
