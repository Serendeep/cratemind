import pytest

from cratemind.config import Settings
from cratemind.download.backends import BackendUnavailable
from cratemind.download.base import Track
from cratemind.runner import run_crate
from cratemind.store.db import CrateStore


def _track(track_id: str) -> Track:
    return Track(spotify_id=track_id, title=f"T{track_id}", artist="A")


def test_run_processes_every_track_and_records_state():
    store = CrateStore()
    seen: list[str] = []

    def fetch(_url, _settings):
        return "spotdl", [_track("1"), _track("2")]

    def process(track, _settings):
        seen.append(track.spotify_id)
        return track.update(status="sorted", bpm=120, bpm_bucket="120-127")

    name, results = run_crate("u", Settings(), store, fetch=fetch, process=process)
    assert name == "spotdl"
    assert seen == ["1", "2"]
    assert all(t.status == "sorted" for t in results)
    assert store.is_done("u", "1")


def test_run_skips_already_sorted_track():
    store = CrateStore()
    store.upsert_track("u", _track("1").update(status="sorted"))
    called: list[str] = []

    def fetch(_url, _settings):
        return "spotdl", [_track("1")]

    def process(track, _settings):
        called.append(track.spotify_id)
        return track.update(status="sorted")

    run_crate("u", Settings(), store, fetch=fetch, process=process)
    assert called == []  # resume skipped re-analysis


def test_resume_returns_stored_analysis_not_blank():
    store = CrateStore()
    store.upsert_track(
        "u",
        Track(
            spotify_id="1", title="T", artist="A",
            genre="techno", bpm=150, bpm_bucket="144-151", key="6A", status="sorted",
        ),
    )

    def fetch(_url, _settings):
        return "spotdl", [Track(spotify_id="1", title="T", artist="A")]  # bare re-download

    _name, results = run_crate("u", Settings(), store, fetch=fetch, process=lambda t, _s: t)
    assert results[0].bpm == 150
    assert results[0].genre == "techno"
    assert results[0].key == "6A"  # read from the store, not the bare file


def test_run_emits_progress_updates():
    store = CrateStore()
    events: list[str] = []

    def fetch(_url, _settings):
        return "spotdl", [_track("1")]

    def process(track, _settings):
        return track.update(status="sorted")

    run_crate(
        "u",
        Settings(),
        store,
        fetch=fetch,
        process=process,
        on_update=lambda t: events.append(t.status),
    )
    assert "downloading" in events
    assert "sorted" in events


def test_run_resumes_from_store_when_fetch_is_empty():
    # Rerun: spotdl re-downloads nothing (everything already sorted), so fetch
    # returns []. The crate must show the stored tracks, not error or go blank.
    store = CrateStore()
    store.upsert_track(
        "u",
        Track(spotify_id="1", title="T", artist="A", genre="techno",
              bpm=150, bpm_bucket="144-151", status="sorted"),
    )
    emitted: list[str] = []

    def fetch(_url, _settings):
        return "spotdl", []

    name, results = run_crate(
        "u", Settings(), store, fetch=fetch,
        process=lambda t, _s: t, on_update=lambda t: emitted.append(t.spotify_id),
    )
    assert name == "spotdl"
    assert [t.spotify_id for t in results] == ["1"]
    assert results[0].genre == "techno"
    assert emitted == ["1"]  # the existing crate was shown


def test_run_raises_when_fetch_empty_and_store_empty():
    store = CrateStore()

    def fetch(_url, _settings):
        return "spotdl", []

    with pytest.raises(BackendUnavailable):
        run_crate("u", Settings(), store, fetch=fetch, process=lambda t, _s: t)
