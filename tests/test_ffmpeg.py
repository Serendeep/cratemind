"""Behaviour of the runtime ffmpeg resolver.

The resolver exists so non-technical users never edit PATH: at startup the app
finds a usable ffmpeg and prepends its directory to this process's PATH, which
child processes (spotdl) inherit. These tests pin the resolution order, the
idempotent PATH mutation, and that a system ffmpeg is left untouched. Filesystem
and subprocess are injected as callables so nothing here touches the real
environment.
"""

from __future__ import annotations

import os
from pathlib import Path

from cratemind import ffmpeg


def _make_exe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


def test_system_ffmpeg_is_used_without_touching_path():
    env = {"PATH": "/usr/bin"}
    found = ffmpeg.ensure_ffmpeg_on_path(
        which=lambda _name: "/usr/bin/ffmpeg",
        candidates=lambda: [Path("/never/looked/at/ffmpeg")],
        environ=env,
    )
    assert found == "/usr/bin/ffmpeg"
    assert env["PATH"] == "/usr/bin"  # untouched


def test_first_usable_candidate_is_prepended(tmp_path):
    binary = _make_exe(tmp_path / "bin" / "ffmpeg")
    env = {"PATH": "/usr/bin"}
    found = ffmpeg.ensure_ffmpeg_on_path(
        which=lambda _name: None,
        candidates=lambda: [tmp_path / "missing" / "ffmpeg", binary],
        environ=env,
    )
    assert found == str(binary)
    assert env["PATH"].split(os.pathsep)[0] == str(binary.parent)
    assert "/usr/bin" in env["PATH"]


def test_prepend_is_idempotent(tmp_path):
    binary = _make_exe(tmp_path / "bin" / "ffmpeg")
    env = {"PATH": "/usr/bin"}
    for _ in range(3):
        ffmpeg.ensure_ffmpeg_on_path(
            which=lambda _name: None,
            candidates=lambda: [binary],
            environ=env,
        )
    assert env["PATH"].split(os.pathsep).count(str(binary.parent)) == 1


def test_returns_none_when_nothing_found():
    env = {"PATH": "/usr/bin"}
    found = ffmpeg.ensure_ffmpeg_on_path(
        which=lambda _name: None,
        candidates=lambda: [Path("/no/ffmpeg")],
        environ=env,
    )
    assert found is None
    assert env["PATH"] == "/usr/bin"


def test_download_ffmpeg_skips_when_already_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("CRATEMIND_CACHE_DIR", str(tmp_path / "cache"))
    cached = _make_exe(ffmpeg.ffmpeg_path())
    calls: list[list[str]] = []

    result = ffmpeg.download_ffmpeg(
        which=lambda _name: "/usr/bin/spotdl",
        run=lambda cmd: calls.append(cmd),
    )
    assert result == cached
    assert calls == []  # no download attempted


def test_download_ffmpeg_consolidates_spotdl_build_into_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CRATEMIND_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path / "home"))
    spotdl_bin = _make_exe(tmp_path / "home" / ".spotdl" / "ffmpeg")

    result = ffmpeg.download_ffmpeg(
        which=lambda _name: "/usr/bin/spotdl",
        run=lambda _cmd: None,  # pretend spotdl already dropped the binary
    )
    assert result == ffmpeg.ffmpeg_path()
    assert result.is_file() and os.access(result, os.X_OK)
    assert spotdl_bin.exists()  # source left in place


def test_download_ffmpeg_raises_when_spotdl_exits_nonzero(tmp_path, monkeypatch):
    # A failed spotdl run must not silently consolidate a stale/corrupt binary
    # left in spotdl's dir from an earlier attempt.
    monkeypatch.setenv("CRATEMIND_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path / "home"))
    _make_exe(tmp_path / "home" / ".spotdl" / "ffmpeg")  # stale binary present

    class _Failed:
        returncode = 1

    try:
        ffmpeg.download_ffmpeg(which=lambda _name: "/usr/bin/spotdl", run=lambda _cmd: _Failed())
    except ffmpeg.FFmpegUnavailable:
        assert not ffmpeg.ffmpeg_path().exists()  # nothing copied into the cache
        return
    raise AssertionError("expected FFmpegUnavailable when spotdl exits non-zero")


def test_download_ffmpeg_requires_spotdl(tmp_path, monkeypatch):
    monkeypatch.setenv("CRATEMIND_CACHE_DIR", str(tmp_path / "cache"))
    try:
        ffmpeg.download_ffmpeg(which=lambda _name: None, run=lambda _cmd: None)
    except ffmpeg.FFmpegUnavailable:
        return
    raise AssertionError("expected FFmpegUnavailable when spotdl is missing")
