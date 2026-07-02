from pathlib import Path

import pytest

from cratemind.config import Settings
from cratemind.download.backends import BackendUnavailable
from cratemind.download.base import Track
from cratemind.runner import apply_crate, run_crate
from cratemind.store.db import CrateStore


def _track(track_id: str) -> Track:
    return Track(spotify_id=track_id, title=f"T{track_id}", artist="A")


def _previewed(track_id: str, tmp_path: Path, genre: str = "techno") -> Track:
    src = tmp_path / f"{track_id}.flac"
    src.write_bytes(b"\x00")
    return Track(
        spotify_id=track_id, title=f"T{track_id}", artist="A", genre=genre,
        bpm=130, bpm_bucket="128-135", file_path=src,
        proposed_path=tmp_path / "out" / genre / "128-135" / f"{track_id}.flac",
        status="previewed",
    )


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


def test_run_surfaces_failed_downloads():
    from pathlib import Path

    store = CrateStore()

    def fetch(_url, _settings):
        return "spotdl", [
            Track(spotify_id="1", title="Got", artist="A", file_path=Path("/x.flac")),
            Track(spotify_id="2", title="Missing", artist="B", status="failed"),
        ]

    _name, results = run_crate(
        "u", Settings(), store, fetch=fetch, process=lambda t, _s: t.update(status="sorted")
    )
    statuses = {t.title: t.status for t in results}
    assert statuses["Missing"] == "failed"
    assert store.status_of("u", "2") == "failed"


def test_run_does_not_reflag_sorted_track_as_failed():
    store = CrateStore()
    store.upsert_track("u", Track(spotify_id="1", title="Song", artist="A", status="sorted"))

    def fetch(_url, _settings):
        # Rerun: nothing new downloaded, but the expected list still names "Song".
        return "spotdl", [Track(spotify_id="9", title="Song", artist="A", status="failed")]

    _name, results = run_crate("u", Settings(), store, fetch=fetch, process=lambda t, _s: t)
    assert [t.status for t in results] == ["sorted"]  # the failed stub was suppressed


def test_run_raises_when_fetch_empty_and_store_empty():
    store = CrateStore()

    def fetch(_url, _settings):
        return "spotdl", []

    with pytest.raises(BackendUnavailable):
        run_crate("u", Settings(), store, fetch=fetch, process=lambda t, _s: t)


def test_previewed_resume_resorts_without_reanalysis(tmp_path):
    # A stored preview re-runs cheap: no process() call, but a newly added
    # alias re-applies and the proposed destination recomputes.
    store = CrateStore()
    store.upsert_track("u", _previewed("1", tmp_path))
    store.set_alias("techno", "warehouse")
    analyzed: list[str] = []

    def fetch(_url, _settings):
        return "spotdl", [_previewed("1", tmp_path)]  # staging re-collected

    _n, results = run_crate(
        "u",
        Settings(output_dir=tmp_path / "out", dry_run=True),
        store,
        fetch=fetch,
        process=lambda t, _s: analyzed.append(t.spotify_id) or t,
    )
    assert analyzed == []  # no librosa re-run
    (track,) = results
    assert track.status == "previewed"
    assert track.genre == "warehouse"
    assert "warehouse" in track.proposed_path.parts
    assert track.file_path.exists()  # still nothing moved


def test_previewed_resume_carries_the_model_confidence(tmp_path):
    # 5A: the model doesn't re-run on a re-preview, so the stored confidence
    # must survive the re-sort instead of being blanked.
    store = CrateStore()
    store.upsert_track("u", _previewed("1", tmp_path).update(genre_confidence=0.83))

    _n, results = run_crate(
        "u",
        Settings(output_dir=tmp_path / "out", dry_run=True),
        store,
        fetch=lambda _u, _s: ("spotdl", []),
        process=lambda t, _s: t,
    )
    (track,) = results
    assert track.status == "previewed"
    assert track.genre_confidence == 0.83


def test_previewed_resume_keeps_sorted_rows_untouched(tmp_path):
    # Regression: mixing previewed rows into a run must not disturb the
    # wholesale skip for sorted ones.
    store = CrateStore()
    store.upsert_track("u", _track("1").update(status="sorted", genre="house"))
    store.upsert_track("u", _previewed("2", tmp_path))
    processed: list[str] = []

    _n, results = run_crate(
        "u",
        Settings(output_dir=tmp_path / "out", dry_run=True),
        store,
        fetch=lambda _u, _s: ("spotdl", []),
        process=lambda t, _s: processed.append(t.spotify_id) or t,
    )
    assert processed == []
    by_id = {t.spotify_id: t for t in results}
    assert by_id["1"].status == "sorted" and by_id["1"].genre == "house"
    assert by_id["2"].status == "previewed"


def test_rerun_without_dry_run_applies_previewed_tracks(tmp_path):
    # Re-running with the preview box unticked performs the moves via the
    # same cheap re-sort path — no re-analysis.
    store = CrateStore()
    store.upsert_track("u", _previewed("1", tmp_path))

    _n, results = run_crate(
        "u",
        Settings(output_dir=tmp_path / "out"),
        store,
        fetch=lambda _u, _s: ("spotdl", []),
        process=lambda t, _s: t,
    )
    (track,) = results
    assert track.status == "sorted"
    assert track.file_path.exists()
    assert track.file_path.is_relative_to(tmp_path / "out")
    assert store.status_of("u", "1") == "sorted"


def test_rerun_degrades_vanished_previewed_file_and_continues(tmp_path):
    # Red team: the re-sort loop is a second apply path. A staged file that
    # vanished must fail that one track, not abort the whole run mid-loop.
    store = CrateStore()
    gone = _previewed("1", tmp_path)
    gone.file_path.unlink()
    store.upsert_track("u", gone)
    store.upsert_track("u", _previewed("2", tmp_path))

    _n, results = run_crate(
        "u",
        Settings(output_dir=tmp_path / "out"),  # preview unticked → moves
        store,
        fetch=lambda _u, _s: ("spotdl", []),
        process=lambda t, _s: t,
    )
    by_id = {t.spotify_id: t for t in results}
    assert by_id["1"].status == "failed"
    assert by_id["2"].status == "sorted"  # the loop carried on
    assert by_id["2"].file_path.exists()


def test_rerun_skips_rows_a_concurrent_apply_already_sorted(tmp_path):
    # Red team: re-run re-checks live status per track under the lock, so it
    # can't overwrite a fresh "sorted" row back to "previewed" or double-move.
    class RacedStore:
        def __init__(self, inner):
            self.inner = inner

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def status_of(self, run_url, spotify_id):
            return "sorted"  # a concurrent Apply won between load and act

    store = CrateStore()
    track = _previewed("1", tmp_path)
    store.upsert_track("u", track)

    _n, results = run_crate(
        "u",
        Settings(output_dir=tmp_path / "out"),
        RacedStore(store),
        fetch=lambda _u, _s: ("spotdl", []),
        process=lambda t, _s: t,
    )
    assert track.file_path.exists()  # nothing moved by the re-run
    assert store.status_of("u", "1") == "previewed"  # row not overwritten


def test_apply_crate_moves_previewed_and_skips_the_rest(tmp_path):
    store = CrateStore()
    store.upsert_track("u", _track("1").update(status="sorted"))
    store.upsert_track("u", _previewed("2", tmp_path))
    applied: list[str] = []

    def fake_apply(track, _settings):
        applied.append(track.spotify_id)
        return track.update(status="sorted", file_path=track.proposed_path, proposed_path=None)

    emitted: list[str] = []
    name, results = apply_crate(
        "u", Settings(), store, apply=fake_apply,
        on_update=lambda t: emitted.append(t.spotify_id),
    )
    assert name == "apply"
    assert applied == ["2"]  # only the previewed row moved
    assert sorted(emitted) == ["1", "2"]  # but the whole crate re-emitted
    assert store.status_of("u", "2") == "sorted"


def test_apply_crate_is_idempotent_on_a_second_run(tmp_path):
    store = CrateStore()
    store.upsert_track("u", _previewed("1", tmp_path))
    applied: list[str] = []

    def fake_apply(track, _settings):
        applied.append(track.spotify_id)
        return track.update(status="sorted", proposed_path=None)

    apply_crate("u", Settings(), store, apply=fake_apply)
    apply_crate("u", Settings(), store, apply=fake_apply)  # double click
    assert applied == ["1"]  # second pass applied nothing
    assert store.status_of("u", "1") == "sorted"  # and never regressed to failed
