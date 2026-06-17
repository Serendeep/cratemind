"""Self-update for the globally-installed app.

cratemind installs as a uv tool (`uv tool install "cratemind @ git+…@<tag>"`), so
the `cratemind` command lives on PATH and there is no source tree to patch. This
module updates the app the way it was installed: it asks the GitHub Releases API
for the latest version and, on request, runs `uv tool install --force` for that
release's tag, which rebuilds the tool from the new source. The heavy artifacts
(genre model, ffmpeg) live in the user cache, not the tool venv, so an update
never re-downloads them.

The audio-genre extra is reinstalled only when it's already present, so updating
never silently pulls the onnxruntime stack onto an install that skipped it.

Network (`fetch_json`) and subprocess (`run`) are injected as callables with real
defaults, so the decision logic and command construction are testable without
touching the network or the system.

Every step fails safe: an unparseable version, a network error, or a malformed
release is treated as "no update", never an exception in the user's face. A
source checkout is refused outright — contributors update with `git pull`.
"""

from __future__ import annotations

import importlib.util
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

REPO = "Serendeep/cratemind"
_LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"

# Injected dependency contracts.
JsonFetcher = Callable[[str], dict[str, object]]
Runner = Callable[[list[str]], object]


@dataclass(frozen=True)
class Release:
    version: str


def current_version() -> str:
    try:
        return version("cratemind")
    except PackageNotFoundError:
        return "0.0.0"  # running from an unbuilt checkout; treat as oldest


def _version_tuple(raw: str) -> tuple[int, ...] | None:
    """Parse 'v1.2.3' / '1.2.3' into a comparable tuple, or None if not numeric."""
    cleaned = raw.strip().lstrip("vV")
    parts = cleaned.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def is_newer(remote: str, local: str) -> bool:
    """True only when `remote` parses as a strictly higher version than `local`."""
    remote_parts, local_parts = _version_tuple(remote), _version_tuple(local)
    if remote_parts is None or local_parts is None:
        return False  # fail safe: never act on a version we can't compare
    # Pad to equal length so "0.1" and "0.1.0" compare equal (not "newer").
    width = max(len(remote_parts), len(local_parts))
    remote_parts += (0,) * (width - len(remote_parts))
    local_parts += (0,) * (width - len(local_parts))
    return remote_parts > local_parts


def _fetch_json(url: str) -> dict[str, object]:
    import httpx

    # Short connect timeout so an offline machine fails fast on launch rather
    # than stalling the startup check.
    response = httpx.get(
        url, timeout=httpx.Timeout(connect=3, read=10, write=10, pool=10), follow_redirects=True
    )
    _ = response.raise_for_status()
    return response.json()


def latest_release(*, fetch_json: JsonFetcher = _fetch_json) -> Release | None:
    """The latest published release tag, or None if it can't be fetched/parsed."""
    try:
        data = fetch_json(_LATEST_URL)
        tag = data.get("tag_name")
    except Exception:  # network, JSON, or HTTP error — treat as "no info"
        return None
    if not isinstance(tag, str):
        return None
    return Release(version=tag)


def install_spec(tag: str, *, with_audio: bool) -> str:
    """The uv-tool requirement string for a given release tag.

    A PEP 508 direct reference (`name[extra] @ git+url@ref`) so uv builds the tool
    from that exact tag, pulling the audio-genre extra only when asked.
    """
    extra = "[audio-genre]" if with_audio else ""
    return f"cratemind{extra} @ git+https://github.com/{REPO}@{tag}"


def _has_audio_extra() -> bool:
    """Whether the audio-genre stack is installed (onnxruntime is its marker dep)."""
    return importlib.util.find_spec("onnxruntime") is not None


# Generous bound: a git clone + dependency-wheel download over a slow link can
# legitimately run minutes, but it must not hang the terminal forever. A timeout
# surfaces as the "Update failed" status line via run_update's except.
_INSTALL_TIMEOUT_SECONDS = 600


def _run(command: list[str]) -> None:
    _ = subprocess.run(command, check=True, timeout=_INSTALL_TIMEOUT_SECONDS)


def apply_update(*, tag: str, with_audio: bool, run: Runner = _run) -> None:
    """Reinstall the tool from `tag`, force-replacing the current install."""
    _ = run(["uv", "tool", "install", "--force", install_spec(tag, with_audio=with_audio)])


def check_and_notify(
    *,
    current: Callable[[], str] = current_version,
    latest: Callable[[], Release | None] = latest_release,
) -> None:
    """Print a one-line notice if a newer release exists. Best-effort; never raises."""
    try:
        release = latest()
        if release and is_newer(release.version, current()):
            tag = release.version.lstrip("vV")
            print(f"A new version is available ({tag}). Run `cratemind update` to upgrade.")
    except Exception:
        pass  # update checks must never block or break a normal launch


_CHECK_INTERVAL_SECONDS = 24 * 60 * 60


def _check_stamp() -> Path:
    import platformdirs

    return Path(platformdirs.user_cache_dir("cratemind")) / "last-update-check"


def notify_if_due(
    *,
    now: Callable[[], float] = time.time,
    stamp_path: Callable[[], Path] = _check_stamp,
    check: Callable[[], None] = check_and_notify,
) -> None:
    """Run the launch notice at most once per 24h, so most launches hit no network."""
    moment = now()  # capture once so the due check and the stamped value agree
    try:
        stamp = stamp_path()
        last = float(stamp.read_text()) if stamp.exists() else 0.0
        if moment - last < _CHECK_INTERVAL_SECONDS:
            return
        stamp.parent.mkdir(parents=True, exist_ok=True)
        _ = stamp.write_text(str(moment))
    except Exception:
        # Can't persist the throttle (e.g. read-only cache) -> skip rather than
        # check on every launch, preserving the <=1/day guarantee.
        return
    check()


def _is_source_checkout() -> bool:
    """True when running from the repo source tree (a sibling pyproject.toml).

    A wheel/tool install resolves this path into site-packages, where no
    pyproject.toml sits — that's the updatable case.
    """
    # This file is src/cratemind/update.py, so parents[2] is the repo root in a
    # src-layout checkout. Tied to that layout; revisit if the package moves.
    return (Path(__file__).resolve().parents[2] / "pyproject.toml").exists()


def run_update(
    *,
    is_source: Callable[[], bool] = _is_source_checkout,
    latest: Callable[[], Release | None] = latest_release,
    current: Callable[[], str] = current_version,
    has_audio: Callable[[], bool] = _has_audio_extra,
    apply: Callable[..., None] = apply_update,
) -> str:
    """User-facing update: fetch latest, reinstall if newer, return a status line."""
    if is_source():
        return (
            "This is a source checkout — update it with `git pull`. "
            "`cratemind update` upgrades the installed app."
        )
    release = latest()
    if release is None:
        return "Couldn't reach GitHub to check for updates."
    if not is_newer(release.version, current()):
        return f"Already up to date (v{current()})."
    try:
        apply(tag=release.version, with_audio=has_audio())
    except Exception as exc:  # build/install failure -> status line, not a traceback
        return f"Update failed: {exc}. Your install is unchanged; try again later."
    return f"Updated to {release.version.lstrip('vV')}. Restart cratemind to use it."
