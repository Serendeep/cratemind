"""Optional share-link upload for an exported crate.json.

Uploads to a free, no-account host — catbox.moe first, 0x0.st as fallback — and
returns the link for the user to copy. No secrets, nothing hardcoded but the
public host URLs. The `post` callable is injectable so this is testable offline.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

CATBOX_URL = "https://catbox.moe/user/api.php"
NULLPOINTER_URL = "https://0x0.st"
Poster = Callable[..., Any]


class ShareError(RuntimeError):
    """Raised when an upload fails or returns something that isn't a URL."""


def _ok_url(text: str) -> str:
    url = text.strip()
    if not url.startswith("http"):
        raise ShareError(f"host did not return a URL: {url[:80]!r}")
    return url


def upload_catbox(path: Path, *, post: Poster = httpx.post) -> str:
    response = post(
        CATBOX_URL,
        data={"reqtype": "fileupload"},
        files={"fileToUpload": (path.name, path.read_bytes())},
        timeout=30,
    )
    response.raise_for_status()
    return _ok_url(response.text)


def upload_0x0(path: Path, *, post: Poster = httpx.post) -> str:
    response = post(
        NULLPOINTER_URL,
        files={"file": (path.name, path.read_bytes())},
        timeout=30,
    )
    response.raise_for_status()
    return _ok_url(response.text)


def share_crate(
    path: Path,
    *,
    primary: Callable[[Path], str] = upload_catbox,
    fallback: Callable[[Path], str] = upload_0x0,
) -> str:
    """Upload via the primary host; fall back to the secondary on any failure."""
    try:
        return primary(path)
    except Exception:
        return fallback(path)
