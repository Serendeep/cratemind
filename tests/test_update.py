"""Behaviour of the self-update logic.

Users without git update by re-running an install; this module lets the app do
it for them: check the latest GitHub release, and on request download + extract
it over the install and re-sync. Network and subprocess are injected as
callables so these tests touch neither — only the pure decision logic and the
extract/swap mechanics against a temp dir are exercised here.
"""

from __future__ import annotations

import io
import zipfile

from cratemind import update


def test_is_newer_compares_semver_ignoring_v_prefix():
    assert update.is_newer("v0.2.0", "0.1.0") is True
    assert update.is_newer("0.1.1", "0.1.0") is True
    assert update.is_newer("v0.1.0", "0.1.0") is False  # same version
    assert update.is_newer("0.1.0", "0.2.0") is False  # older remote


def test_is_newer_is_false_on_unparseable_version():
    # Never nag/update on a tag we can't parse — fail safe.
    assert update.is_newer("nightly", "0.1.0") is False


def test_latest_release_parses_tag_and_zipball():
    payload = {"tag_name": "v0.3.0", "zipball_url": "https://example/zip", "name": "0.3.0"}
    rel = update.latest_release(fetch_json=lambda _url: payload)
    assert rel is not None
    assert rel.version == "v0.3.0"
    assert rel.zipball_url == "https://example/zip"


def test_latest_release_returns_none_on_fetch_error():
    def boom(_url):
        raise OSError("network down")

    assert update.latest_release(fetch_json=boom) is None


def test_check_and_notify_is_silent_when_up_to_date(capsys):
    update.check_and_notify(
        current=lambda: "0.1.0",
        latest=lambda: update.Release(version="v0.1.0", zipball_url="x"),
    )
    assert capsys.readouterr().out == ""


def test_check_and_notify_prints_when_newer(capsys):
    update.check_and_notify(
        current=lambda: "0.1.0",
        latest=lambda: update.Release(version="v0.2.0", zipball_url="x"),
    )
    out = capsys.readouterr().out
    assert "0.2.0" in out
    assert "cratemind update" in out


def test_check_and_notify_swallows_errors(capsys):
    def boom():
        raise RuntimeError("offline")

    update.check_and_notify(current=lambda: "0.1.0", latest=boom)  # must not raise
    assert capsys.readouterr().out == ""


def test_notify_if_due_skips_when_checked_recently(tmp_path):
    stamp = tmp_path / "last-check"
    stamp.write_text("1000.0")
    calls: list[int] = []
    update.notify_if_due(
        now=lambda: 1000.0 + 60,  # 1 minute later, well within 24h
        stamp_path=lambda: stamp,
        check=lambda: calls.append(1),
    )
    assert calls == []  # throttled, no network check


def test_notify_if_due_runs_and_stamps_when_due(tmp_path):
    stamp = tmp_path / "last-check"
    stamp.write_text("1000.0")  # last checked long ago
    calls: list[int] = []
    update.notify_if_due(
        now=lambda: 1000.0 + 90_000,  # >24h later -> due
        stamp_path=lambda: stamp,
        check=lambda: calls.append(1),
    )
    assert calls == [1]  # check performed
    assert stamp.read_text() == "91000.0"  # timestamp recorded


def _zip_bytes(files: dict[str, str]) -> bytes:
    # GitHub zipballs nest everything under a top-level <owner>-<repo>-<sha>/ dir.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(f"Serendeep-cratemind-abc123/{name}", content)
    return buf.getvalue()


def test_apply_update_skips_path_traversal_entries(tmp_path):
    # A crafted zip with a `..` member must not write outside install_dir.
    install = tmp_path / "app"
    install.mkdir()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Serendeep-cratemind-abc123/ok.py", "ok")
        # Strips to "../evil.py" -> would land in tmp_path (outside install).
        zf.writestr("Serendeep-cratemind-abc123/../evil.py", "pwned")

    update.apply_update(
        zipball_url="x",
        install_dir=install,
        download=lambda _url: buf.getvalue(),
        run=lambda _cmd, _cwd: None,
    )
    assert (install / "ok.py").read_text() == "ok"
    assert not (tmp_path / "evil.py").exists()  # traversal blocked, not written outside install


def test_apply_update_extracts_over_install_and_syncs(tmp_path):
    install = tmp_path / "app"
    (install / "src").mkdir(parents=True)
    (install / "src" / "old.py").write_text("old")
    zbytes = _zip_bytes({"src/new.py": "new", "pyproject.toml": "x"})
    synced: list[list[str]] = []

    update.apply_update(
        zipball_url="https://example/zip",
        install_dir=install,
        download=lambda _url: zbytes,
        run=lambda cmd, cwd: synced.append(cmd),
    )
    # New files land at the install root (top-level zip dir stripped).
    assert (install / "src" / "new.py").read_text() == "new"
    assert (install / "pyproject.toml").exists()
    assert synced == [["uv", "sync"]]  # re-sync after extract
