"""Self-update from GitHub Releases, for users who installed without git.

The supported install path is "download the repo, run setup, run the app" — no
git, so `git pull` is not an option. This module lets the app update itself: it
asks the GitHub Releases API for the latest version, and on request downloads
that release's source zip, extracts it over the install directory, and re-syncs
dependencies. The heavy artifacts (genre model, ffmpeg) live in the user cache,
not the install dir, so an update never re-downloads them.

Network (`fetch_json`/`download`) and subprocess (`run`) are injected as
callables with real defaults, so the decision logic and extract/swap mechanics
are testable without touching the network or the filesystem outside a temp dir.

Every step fails safe: an unparseable version, a network error, or a malformed
release is treated as "no update", never an exception in the user's face.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

REPO = "Serendeep/cratemind"
_LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"

# Injected dependency contracts.
JsonFetcher = Callable[[str], dict[str, object]]
Downloader = Callable[[str], bytes]
Runner = Callable[[list[str], Path], object]


@dataclass(frozen=True)
class Release:
    version: str
    zipball_url: str


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
    response = httpx.get(url, timeout=httpx.Timeout(connect=3, read=10, write=10, pool=10), follow_redirects=True)
    _ = response.raise_for_status()
    return response.json()


def latest_release(*, fetch_json: JsonFetcher = _fetch_json) -> Release | None:
    """The latest published release, or None if it can't be fetched/parsed."""
    try:
        data = fetch_json(_LATEST_URL)
        tag = data.get("tag_name")
        zipball = data.get("zipball_url")
    except Exception:  # network, JSON, or HTTP error — treat as "no info"
        return None
    if not isinstance(tag, str) or not isinstance(zipball, str):
        return None
    return Release(version=tag, zipball_url=zipball)


def _download(url: str) -> bytes:
    import httpx

    # Bounded read timeout so a stalled CDN can't hang `cratemind update` forever;
    # 300s is generous for a source zip.
    response = httpx.get(
        url, timeout=httpx.Timeout(connect=10, read=300, write=60, pool=10), follow_redirects=True
    )
    _ = response.raise_for_status()
    return response.content


def _run(command: list[str], cwd: Path) -> None:
    _ = subprocess.run(command, cwd=cwd, check=True)


def apply_update(
    *,
    zipball_url: str,
    install_dir: Path,
    download: Downloader = _download,
    run: Runner = _run,
) -> None:
    """Download the release zip, extract it over `install_dir`, and re-sync.

    GitHub zipballs nest everything under a single top-level ``<owner>-<repo>-<sha>/``
    directory; that prefix is stripped so files land at the install root.
    """
    raw = download(zipball_url)
    root_dir = install_dir.resolve()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.namelist()
        prefix = members[0].split("/", 1)[0] + "/" if members else ""
        for member in members:
            if member.endswith("/") or not member.startswith(prefix):
                continue
            relative = member[len(prefix) :]
            dest = (install_dir / relative).resolve()
            # Guard against zip-slip: a crafted "../" entry must not escape the
            # install dir. Silently skip anything that would write outside it.
            if not dest.is_relative_to(root_dir):
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, dest.open("wb") as out:
                _ = shutil.copyfileobj(src, out)
    _ = run(["uv", "sync"], install_dir)


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


def run_update(install_dir: Path | None = None) -> str:
    """User-facing update: fetch latest, apply if newer, return a status line."""
    here = install_dir or Path(__file__).resolve().parents[2]
    # Only the source-tree layout is updatable in place. A wheel install resolves
    # `here` to site-packages; refuse rather than extract a zip over it.
    if not (here / "pyproject.toml").exists():
        return (
            "Can't self-update: this doesn't look like a source install. "
            "Download the latest release and re-run the setup script instead."
        )
    release = latest_release()
    if release is None:
        return "Couldn't reach GitHub to check for updates."
    if not is_newer(release.version, current_version()):
        return f"Already up to date (v{current_version()})."
    try:
        apply_update(zipball_url=release.zipball_url, install_dir=here)
    except Exception as exc:  # download/unzip/uv sync failure -> status line, not a traceback
        return f"Update failed: {exc}. Your install is unchanged; try again later."
    return f"Updated to {release.version.lstrip('vV')}. Restart cratemind to use it."
