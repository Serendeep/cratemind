from pathlib import Path

import pytest

from cratemind.share import ShareError, share_crate, upload_catbox


class FakeResponse:
    def __init__(self, text: str, status: int = 200) -> None:
        self.text = text
        self._status = status

    def raise_for_status(self) -> None:
        if self._status >= 400:
            raise RuntimeError(f"http {self._status}")


def _crate(tmp_path: Path) -> Path:
    path = tmp_path / "crate.json"
    path.write_text("{}")
    return path


def test_upload_catbox_returns_url(tmp_path):
    def post(_url, **_kw):
        return FakeResponse("https://files.catbox.moe/x.json")

    assert upload_catbox(_crate(tmp_path), post=post) == "https://files.catbox.moe/x.json"


def test_upload_rejects_non_url_response(tmp_path):
    def post(_url, **_kw):
        return FakeResponse("something went wrong")

    with pytest.raises(ShareError):
        upload_catbox(_crate(tmp_path), post=post)


def test_share_crate_falls_back_to_secondary(tmp_path):
    def primary(_p):
        raise ShareError("catbox down")

    def fallback(_p):
        return "https://0x0.st/abc.json"

    assert share_crate(_crate(tmp_path), primary=primary, fallback=fallback) == "https://0x0.st/abc.json"
