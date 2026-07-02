from cratemind.config import Settings
from cratemind.download.base import Track
from cratemind.store.db import CrateStore
from cratemind.web.jobs import JobManager


def _inline() -> JobManager:
    return JobManager(store_factory=CrateStore, spawn=lambda work: work())


def test_job_runs_and_collects_tracks():
    manager = _inline()

    def runner(_url, _settings, _store, *, on_update=None):
        assert on_update is not None
        on_update(Track(spotify_id="1", title="x", artist="y").update(status="downloading"))
        on_update(Track(spotify_id="1", title="x", artist="y").update(status="sorted", bpm=120))
        return "spotdl", []

    job = manager.start("u", Settings(), runner=runner)
    assert job.status == "done"
    assert job.backend == "spotdl"
    assert len(job.tracks) == 1  # de-duped by spotify_id
    assert job.tracks[0].status == "sorted"


def test_job_surfaces_playlist_name():
    manager = _inline()

    def runner(_url, _settings, store, *, on_update=None):
        store.upsert_run("u", name="Friday Bangers")  # what fetch_playlist captures
        return "spotdl", []

    job = manager.start("u", Settings(), runner=runner)
    assert job.playlist_name == "Friday Bangers"


def test_job_records_error():
    manager = _inline()

    def runner(*_a, **_k):
        raise RuntimeError("no usable download backend")

    job = manager.start("u", Settings(), runner=runner)
    assert job.status == "error"
    assert "no usable download backend" in (job.error or "")


def test_get_returns_started_job():
    manager = _inline()
    job = manager.start("u", Settings(), runner=lambda *_a, **_k: ("spotdl", []))
    assert manager.get(job.id) is job


def _capture_dry_run(captured: dict):
    def runner(_url, settings, _store, *, on_update=None):
        captured["dry_run"] = settings.dry_run
        return "local", []

    return runner


def test_local_source_is_forced_into_preview():
    # The safety rule lives at this seam so EVERY route inherits it — including
    # the crates-list re-run, which never sees the run form's checkbox.
    captured: dict = {}
    _inline().start("local:/music/incoming", Settings(), runner=_capture_dry_run(captured))
    assert captured["dry_run"] is True


def test_local_preview_override_is_explicit_only():
    captured: dict = {}
    _inline().start(
        "local:/music/incoming",
        Settings(),
        runner=_capture_dry_run(captured),
        allow_move_local=True,
    )
    assert captured["dry_run"] is False


def test_playlist_urls_keep_the_callers_dry_run():
    captured: dict = {}
    manager = _inline()
    manager.start("https://open.spotify.com/playlist/x", Settings(), runner=_capture_dry_run(captured))
    assert captured["dry_run"] is False
    manager.start(
        "https://open.spotify.com/playlist/x",
        Settings(dry_run=True),
        runner=_capture_dry_run(captured),
    )
    assert captured["dry_run"] is True
