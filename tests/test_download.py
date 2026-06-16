from pathlib import Path

import pytest

from cratemind.download import backends, tags
from cratemind.download.backends import (
    BackendUnavailable,
    SpotdlBackend,
    SpotiFlacBackend,
    build_spotdl_command,
    build_spotiflac_command,
    fetch_playlist,
    select_backends,
)
from cratemind.config import Settings

URL = "https://open.spotify.com/playlist/abc"


def test_select_backends_flac_uses_spotdl():
    # SpotiFLAC is paused; spotdl handles flac (and every format) for now.
    assert [b.name for b in select_backends("flac")] == ["spotdl"]


def test_select_backends_lossy_is_spotdl_only():
    assert [b.name for b in select_backends("mp3")] == ["spotdl"]


def test_spotiflac_supports_only_flac():
    b = SpotiFlacBackend()
    assert b.supports("flac") and not b.supports("mp3")


def test_build_spotdl_command_shape():
    cmd = build_spotdl_command(URL, Path("/out"), "mp3")
    assert cmd[:3] == ["spotdl", "download", URL]
    assert "--format" in cmd and "mp3" in cmd
    assert "--overwrite" in cmd and "skip" in cmd  # skip already-downloaded
    assert "--scan-for-songs" in cmd
    output = cmd[cmd.index("--output") + 1]
    assert output.startswith("/out/")  # template lives inside out_dir
    assert "{title}" in output and "{output-ext}" in output


def test_build_spotiflac_command_is_positional():
    # SpotiFLAC CLI: `spotiflac <url> <output_dir>`
    assert build_spotiflac_command(URL, Path("/out")) == ["spotiflac", URL, "/out"]


def test_is_lossless_by_suffix():
    assert tags.is_lossless(Path("a.flac"))
    assert not tags.is_lossless(Path("a.mp3"))


def test_stable_id_is_deterministic():
    assert tags.stable_id("Kavinsky", "Nightcall") == tags.stable_id("Kavinsky", "Nightcall")
    assert tags.stable_id("A", "B") != tags.stable_id("B", "A")


def test_track_from_file_maps_and_canonicalizes_genre(monkeypatch):
    monkeypatch.setattr(
        tags,
        "read_tags",
        lambda _p: {"title": "Nightcall", "artist": "Kavinsky", "genre": "Drum & Bass"},
    )
    track = tags.track_from_file(Path("/m/nightcall.flac"), source="spotiflac")
    assert track.title == "Nightcall"
    assert track.genre == "drum and bass"  # canonicalized
    assert track.lossless is True
    assert track.source == "spotiflac"
    assert track.status == "downloading"


def test_missing_cli_raises_backend_unavailable(monkeypatch):
    monkeypatch.setattr(backends.shutil, "which", lambda _name: None)
    with pytest.raises(BackendUnavailable):
        SpotdlBackend("mp3").fetch(URL, Path("/tmp/cm-nope"))


def test_fetch_playlist_downloads_into_output_root(monkeypatch, tmp_path):
    settings = Settings(output_dir=tmp_path, audio_format="flac")
    created = tmp_path / "song.mp3"  # downloads land in the output root, not a cache

    def fake_run(command):
        if command[0] == "spotiflac":
            raise BackendUnavailable("spotiflac missing")
        created.write_bytes(b"\x00")

    monkeypatch.setattr(backends, "_run", fake_run)
    monkeypatch.setattr(tags, "read_tags", lambda _p: {"title": "Song", "artist": "X", "genre": None})

    name, tracks, _name = fetch_playlist(URL, settings)
    assert name == "spotdl"
    assert len(tracks) == 1 and tracks[0].source == "spotdl"


def test_fetch_playlist_falls_through_when_backend_downloads_nothing(monkeypatch, tmp_path):
    # SpotiFLAC exits cleanly but its providers are down, so it produces no files.
    settings = Settings(output_dir=tmp_path, audio_format="flac")
    monkeypatch.setattr(
        backends,
        "select_backends",
        lambda _fmt: [backends.SpotiFlacBackend(), backends.SpotdlBackend("mp3")],
    )

    def fake_run(command):
        if command[0] == "spotiflac":
            return  # "succeeds" with zero downloads
        (tmp_path / "song.mp3").write_bytes(b"\x00")

    monkeypatch.setattr(backends, "_run", fake_run)
    monkeypatch.setattr(tags, "read_tags", lambda _p: {"title": "S", "artist": "A", "genre": None})
    name, tracks, _name = fetch_playlist(URL, settings)
    assert name == "spotdl"  # must fall through, not return spotiflac's empty result
    assert len(tracks) == 1


def test_fetch_playlist_returns_empty_when_nothing_new(monkeypatch, tmp_path):
    # Installed backend runs but downloads nothing (a rerun, everything sorted).
    # That's (name, []), NOT an error — the runner decides if it's a real failure.
    settings = Settings(output_dir=tmp_path, audio_format="mp3")
    monkeypatch.setattr(backends, "_run", lambda _cmd: None)  # runs, writes nothing
    name, tracks, _name = fetch_playlist(URL, settings)
    assert name == "spotdl"
    assert tracks == []


def test_fetch_playlist_raises_when_no_backend_installed(monkeypatch, tmp_path):
    settings = Settings(output_dir=tmp_path, audio_format="mp3")

    def fake_run(_cmd):
        raise BackendUnavailable("spotdl is not installed")

    monkeypatch.setattr(backends, "_run", fake_run)
    with pytest.raises(BackendUnavailable):
        fetch_playlist(URL, settings)


def test_fetch_reports_undownloaded_songs_as_failed(monkeypatch, tmp_path):
    import json

    def fake_run(command):
        if command[1] == "save":  # spotdl save -> write the expected tracklist
            save_file = Path(command[command.index("--save-file") + 1])
            save_file.write_text(
                json.dumps([{"name": "Got It", "artist": "A"}, {"name": "Missing", "artist": "B"}])
            )
        else:  # download -> only one of the two songs lands
            (tmp_path / "A - Got It.flac").write_bytes(b"\x00")

    monkeypatch.setattr(backends, "_run", fake_run)
    monkeypatch.setattr(tags, "read_tags", lambda _p: {"title": "Got It", "artist": "A", "genre": None})
    tracks = SpotdlBackend("flac").fetch(URL, tmp_path)
    statuses = {t.title: t.status for t in tracks}
    assert statuses["Got It"] == "downloading"  # the file that landed
    assert statuses["Missing"] == "failed"  # spotdl couldn't get it
    assert not (tmp_path / backends.TRACKLIST_FILE).exists()  # tracklist cleaned up


def test_expected_count_reads_tracklist_size(tmp_path):
    import json

    (tmp_path / backends.TRACKLIST_FILE).write_text(
        json.dumps([{"name": "One", "artist": "A"}, {"name": "Two", "artist": "B"}])
    )
    assert backends.expected_count(tmp_path) == 2


def test_expected_count_zero_when_no_tracklist_or_corrupt(tmp_path):
    assert backends.expected_count(tmp_path) == 0  # no save-file yet (SpotiFLAC, or pre-save)
    (tmp_path / backends.TRACKLIST_FILE).write_text("{not json")
    assert backends.expected_count(tmp_path) == 0  # corrupt -> 0, never raises


def test_expected_count_zero_for_non_list_json(tmp_path):
    # A format change (object/string instead of a list) must not be miscounted:
    # len({}) is 0 and len("abc") is 3 — both wrong — so guard on list-ness.
    (tmp_path / backends.TRACKLIST_FILE).write_text('{"tracks": [1, 2, 3]}')
    assert backends.expected_count(tmp_path) == 0


def test_fetch_returns_partial_files_when_backend_crashes(monkeypatch, tmp_path):
    # A mid-download crash still leaves files in the root — process them, don't orphan.
    def fake_run(_command):
        (tmp_path / "partial.flac").write_bytes(b"\x00")
        raise BackendUnavailable("spotdl crashed mid-download")

    monkeypatch.setattr(backends, "_run", fake_run)
    monkeypatch.setattr(tags, "read_tags", lambda _p: {"title": "t", "artist": "a", "genre": None})
    tracks = SpotdlBackend("flac").fetch(URL, tmp_path)
    assert {t.file_path.name for t in tracks if t.file_path} == {"partial.flac"}


def test_fetch_reraises_when_crash_left_nothing(monkeypatch, tmp_path):
    def fake_run(_command):
        raise BackendUnavailable("not installed")

    monkeypatch.setattr(backends, "_run", fake_run)
    with pytest.raises(BackendUnavailable):
        SpotdlBackend("flac").fetch(URL, tmp_path)


def test_fetch_scans_output_root_not_subfolders(monkeypatch, tmp_path):
    # A prior run's sorted file lives in a subfolder; only the root staging file
    # is fresh. fetch returns just the root file (spotdl skips the sorted one).
    (tmp_path / "techno" / "144-151").mkdir(parents=True)
    (tmp_path / "techno" / "144-151" / "sorted.flac").write_bytes(b"\x00")

    def fake_run(_command):
        (tmp_path / "new.flac").write_bytes(b"\x00")  # fresh download into the root

    monkeypatch.setattr(backends, "_run", fake_run)
    monkeypatch.setattr(tags, "read_tags", lambda _p: {"title": "t", "artist": "a", "genre": None})
    tracks = SpotdlBackend("flac").fetch(URL, tmp_path)
    assert {t.file_path.name for t in tracks if t.file_path} == {"new.flac"}  # subfolder ignored
