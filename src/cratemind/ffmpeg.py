"""Make ffmpeg available to spotdl at runtime without the user touching PATH.

spotdl transcodes downloads with ffmpeg, but non-technical users should never
have to edit their shell PATH or move binaries around. So rather than installing
ffmpeg globally, the app locates a usable binary at startup and prepends its
directory to *this process's* PATH. Child processes (spotdl, SpotiFLAC) inherit
that environment, so they find ffmpeg with zero shell configuration.

Resolution order, cheapest first:
  1. a system ffmpeg already on PATH  -> use as-is, never mutate the environment
  2. cratemind's own cached copy        -> prepend its dir to PATH
  3. spotdl's portable download         -> prepend its dir to PATH

The cached copy lives beside the genre model under ``user_cache_dir("cratemind")``
(overridable with ``CRATEMIND_CACHE_DIR``), so it survives a fresh ZIP download
— the update path for users without git — and is never re-fetched. The spotdl
locations are accepted as a fallback so the shell installer can simply run
``spotdl --download-ffmpeg`` without an ordering dependency on the app being
installed first.

``download_ffmpeg`` reuses spotdl's per-OS static build instead of
reimplementing platform detection, then consolidates it into the cache so the
cache dir is the one canonical, app-owned home. External dependencies (PATH
lookup, subprocess) are injected as callables with real defaults so tests need
no patching.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, MutableMapping
from pathlib import Path

import platformdirs

# Named callable contracts for the injected dependencies.
WhichFn = Callable[[str], str | None]
RunFn = Callable[[list[str]], object]
CandidatesFn = Callable[[], Iterable[Path]]

_EXE = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"


class FFmpegUnavailable(RuntimeError):
    """Raised when ffmpeg cannot be acquired (e.g. spotdl is not installed)."""


def cache_dir() -> Path:
    """Directory holding cratemind's own ffmpeg copy (mirrors prefs' override)."""
    override = os.environ.get("CRATEMIND_CACHE_DIR")
    base = Path(override) if override else Path(platformdirs.user_cache_dir("cratemind"))
    return base / "bin"


def ffmpeg_path() -> Path:
    return cache_dir() / _EXE


def _spotdl_candidates() -> list[Path]:
    # Where `spotdl --download-ffmpeg` drops the binary: ~/.spotdl on macOS/Windows,
    # ~/.config/spotdl under XDG on Linux. Mirrors spotdl.utils.config.get_spotdl_path.
    home = Path.home()
    return [home / ".spotdl" / _EXE, home / ".config" / "spotdl" / _EXE]


def candidate_paths() -> list[Path]:
    """Known local ffmpeg locations, preferred first (cratemind's, then spotdl's)."""
    return [ffmpeg_path(), *_spotdl_candidates()]


def _usable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _prepend_path(environ: MutableMapping[str, str], directory: str) -> None:
    parts = [p for p in environ.get("PATH", "").split(os.pathsep) if p]
    if directory in parts:
        return
    environ["PATH"] = os.pathsep.join([directory, *parts])


def ensure_ffmpeg_on_path(
    *,
    which: WhichFn = shutil.which,
    candidates: CandidatesFn = candidate_paths,
    environ: MutableMapping[str, str] | None = None,
) -> str | None:
    """Guarantee ffmpeg is findable by child processes; return its path or None.

    A system ffmpeg is left untouched. Otherwise the first usable candidate's
    directory is prepended to PATH (idempotent — never added twice).
    """
    env = os.environ if environ is None else environ
    found = which("ffmpeg")
    if found:
        return found
    for path in candidates():
        if _usable(path):
            _prepend_path(env, str(path.parent))
            return str(path)
    return None


def download_ffmpeg(
    *,
    which: WhichFn = shutil.which,
    run: RunFn = subprocess.run,
) -> Path:
    """Fetch spotdl's portable ffmpeg into cratemind's cache (idempotent).

    Returns the cached path. Skips the download entirely when a cached copy
    already exists, so re-running setup never re-downloads. Requires spotdl.
    """
    dest = ffmpeg_path()
    if _usable(dest):
        return dest
    if which("spotdl") is None:
        raise FFmpegUnavailable("spotdl is required to download ffmpeg; install spotdl first")
    result = run(["spotdl", "--download-ffmpeg"])
    # Don't trust a binary on disk if the run failed — it may be a stale or
    # half-written copy from an earlier attempt.
    returncode = getattr(result, "returncode", 0)
    if returncode:
        raise FFmpegUnavailable(f"'spotdl --download-ffmpeg' failed (exit {returncode})")
    source = next((p for p in _spotdl_candidates() if _usable(p)), None)
    if source is None:
        raise FFmpegUnavailable("'spotdl --download-ffmpeg' did not produce an ffmpeg binary")
    dest.parent.mkdir(parents=True, exist_ok=True)
    _ = shutil.copy2(source, dest)
    dest.chmod(dest.stat().st_mode | 0o111)  # ensure the executable bit survives the copy
    return dest
