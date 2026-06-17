"""Behaviour of the self-update logic.

cratemind installs as a uv tool (`uv tool install`), so updating means
reinstalling the tool from the latest GitHub release tag — not patching a source
tree. This module checks the latest release and, on request, runs
`uv tool install --force` for the new tag. Network and subprocess are injected as
callables so these tests touch neither: only the pure decision logic and the
command construction are exercised here.
"""

from __future__ import annotations

from cratemind import update


def test_is_newer_compares_semver_ignoring_v_prefix():
    assert update.is_newer("v0.2.0", "0.1.0") is True
    assert update.is_newer("0.1.1", "0.1.0") is True
    assert update.is_newer("v0.1.0", "0.1.0") is False  # same version
    assert update.is_newer("0.1.0", "0.2.0") is False  # older remote
    # Trailing-.0 segments must compare equal, not "newer" (tuple-length guard).
    assert update.is_newer("0.1.0", "0.1") is False
    assert update.is_newer("0.1", "0.1.0") is False


def test_is_newer_is_false_on_unparseable_version():
    # Never nag/update on a tag we can't parse — fail safe.
    assert update.is_newer("nightly", "0.1.0") is False


def test_latest_release_parses_tag():
    payload = {"tag_name": "v0.3.0", "name": "0.3.0"}
    rel = update.latest_release(fetch_json=lambda _url: payload)
    assert rel is not None
    assert rel.version == "v0.3.0"


def test_latest_release_returns_none_on_missing_tag():
    rel = update.latest_release(fetch_json=lambda _url: {"name": "0.3.0"})
    assert rel is None


def test_latest_release_returns_none_on_fetch_error():
    def boom(_url):
        raise OSError("network down")

    assert update.latest_release(fetch_json=boom) is None


def test_check_and_notify_is_silent_when_up_to_date(capsys):
    update.check_and_notify(
        current=lambda: "0.1.0",
        latest=lambda: update.Release(version="v0.1.0"),
    )
    assert capsys.readouterr().out == ""


def test_check_and_notify_prints_when_newer(capsys):
    update.check_and_notify(
        current=lambda: "0.1.0",
        latest=lambda: update.Release(version="v0.2.0"),
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


def test_notify_if_due_skips_check_when_stamp_unwritable():
    # A read-only/invalid cache must skip the check, not fall back to every launch.
    def boom() -> object:
        raise OSError("read-only cache")

    calls: list[int] = []
    update.notify_if_due(now=lambda: 1e9, stamp_path=boom, check=lambda: calls.append(1))
    assert calls == []


def test_install_spec_includes_audio_extra_when_requested():
    spec = update.install_spec("v0.3.0", with_audio=True)
    assert spec == "cratemind[audio-genre] @ git+https://github.com/Serendeep/cratemind@v0.3.0"


def test_install_spec_omits_extra_without_audio():
    spec = update.install_spec("v0.3.0", with_audio=False)
    assert spec == "cratemind @ git+https://github.com/Serendeep/cratemind@v0.3.0"


def test_apply_update_runs_uv_tool_install_with_spec():
    commands: list[list[str]] = []
    update.apply_update(tag="v0.3.0", with_audio=True, run=lambda cmd: commands.append(cmd))
    assert commands == [
        [
            "uv",
            "tool",
            "install",
            "--force",
            "cratemind[audio-genre] @ git+https://github.com/Serendeep/cratemind@v0.3.0",
        ]
    ]


def test_run_update_refuses_source_checkout():
    message = update.run_update(is_source=lambda: True)
    assert "git pull" in message


def test_run_update_reports_unreachable_github():
    message = update.run_update(is_source=lambda: False, latest=lambda: None)
    assert "Couldn't reach GitHub" in message


def test_run_update_is_noop_when_up_to_date():
    message = update.run_update(
        is_source=lambda: False,
        latest=lambda: update.Release("v0.1.0"),
        current=lambda: "0.1.0",
    )
    assert "Already up to date" in message
    assert "0.1.0" in message


def test_run_update_applies_when_newer_and_passes_audio_flag():
    applied: list[tuple[str, bool]] = []
    message = update.run_update(
        is_source=lambda: False,
        latest=lambda: update.Release("v9.9.9"),
        current=lambda: "0.1.0",
        has_audio=lambda: True,
        apply=lambda *, tag, with_audio: applied.append((tag, with_audio)),
    )
    assert applied == [("v9.9.9", True)]
    assert "Updated to 9.9.9" in message


def test_run_update_returns_status_line_when_apply_fails():
    def boom(**_kwargs) -> None:
        raise RuntimeError("uv tool install exploded")

    message = update.run_update(
        is_source=lambda: False,
        latest=lambda: update.Release("v9.9.9"),
        current=lambda: "0.1.0",
        has_audio=lambda: False,
        apply=boom,
    )
    assert "Update failed" in message  # status line, not a traceback
    assert "unchanged" in message
