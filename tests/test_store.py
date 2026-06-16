from pathlib import Path

from cratemind.download.base import Track
from cratemind.store.db import CrateStore, run_id_for


def _track(**overrides) -> Track:
    base = {"spotify_id": "1", "title": "Nightcall", "artist": "Kavinsky"}
    base.update(overrides)
    return Track(**base)  # type: ignore[arg-type]


def test_upsert_and_read_roundtrip():
    store = CrateStore()
    store.upsert_track(
        "u",
        _track(
            genre="synthwave",
            bpm=118,
            bpm_bucket="112-119",
            source="spotiflac",
            lossless=True,
            file_path=Path("/m/a.flac"),
            status="sorted",
        ),
    )
    (track,) = store.tracks("u")
    assert track.title == "Nightcall"
    assert track.bpm == 118
    assert track.lossless is True
    assert track.file_path == Path("/m/a.flac")
    assert track.status == "sorted"
    store.close()


def test_upsert_updates_existing_status_and_does_not_duplicate():
    store = CrateStore()
    store.upsert_track("u", _track(status="downloading"))
    store.upsert_track("u", _track(status="sorted"))
    assert store.status_of("u", "1") == "sorted"
    assert store.is_done("u", "1")
    assert len(store.tracks("u")) == 1
    store.close()


def test_is_done_false_for_pending():
    store = CrateStore()
    store.upsert_track("u", _track(status="queued"))
    assert not store.is_done("u", "1")
    store.close()


def test_settings_roundtrip():
    store = CrateStore()
    store.set_setting("format", "flac")
    assert store.get_setting("format") == "flac"
    assert store.get_setting("missing") is None
    store.close()


def test_alias_map_roundtrip():
    store = CrateStore()
    store.set_alias("dnb", "drum and bass")
    assert store.aliases() == {"dnb": "drum and bass"}
    store.close()


def test_delete_alias_removes_entry():
    store = CrateStore()
    store.set_alias("dnb", "drum and bass")
    store.set_alias("edm", "electronic")
    store.delete_alias("dnb")
    assert store.aliases() == {"edm": "electronic"}
    store.delete_alias("missing")  # deleting a non-existent alias is a no-op
    assert store.aliases() == {"edm": "electronic"}
    store.close()


def test_run_id_for_is_stable():
    assert run_id_for("u") == run_id_for("u")
    assert len(run_id_for("u")) == 12
    assert run_id_for("u") != run_id_for("v")


def test_runs_lists_with_track_counts():
    store = CrateStore()
    store.upsert_run("u", name="My Set")
    store.upsert_track("u", _track(spotify_id="1", status="sorted"))
    store.upsert_track("u", _track(spotify_id="2", status="failed"))
    (run,) = store.runs()
    assert run.name == "My Set"
    assert (run.total, run.sorted, run.failed) == (2, 1, 1)
    assert run.run_id == run_id_for("u")
    store.close()


def test_upsert_run_name_none_keeps_existing():
    store = CrateStore()
    store.upsert_run("u", name="Named")
    store.upsert_run("u", name=None)  # a later touch must not clobber the name
    assert store.runs()[0].name == "Named"
    store.close()


def test_runs_falls_back_to_url_when_unnamed():
    store = CrateStore()
    store.upsert_run("spotify:playlist:x", name=None)
    assert store.runs()[0].name == "spotify:playlist:x"
    store.close()


def test_run_url_for_id_roundtrip():
    store = CrateStore()
    store.upsert_run("u", name="X")
    assert store.run_url_for_id(run_id_for("u")) == "u"
    assert store.run_url_for_id("does-not-exist") is None
    store.close()


def test_persists_to_file(tmp_path):
    db = tmp_path / "cratemind.db"
    store = CrateStore(db)
    store.upsert_track("u", _track(status="sorted"))
    store.close()
    reopened = CrateStore(db)
    assert reopened.is_done("u", "1")
    reopened.close()
