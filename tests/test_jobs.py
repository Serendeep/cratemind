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


def test_monitor_counts_only_this_runs_staging(tmp_path, monkeypatch):
    # Regression: the progress monitor was rescoped from the shared output root
    # to the run's own staging dir — another run's pending preview (and legacy
    # root leftovers) must not inflate this run's downloaded count.
    import time

    from cratemind.download import backends

    settings = Settings(output_dir=tmp_path)
    url = "https://open.spotify.com/playlist/mine"
    mine = backends.staging_dir(url, settings)
    mine.mkdir(parents=True)
    (mine / "a.mp3").write_bytes(b"\x00")
    (mine / "b.mp3").write_bytes(b"\x00")
    other = backends.staging_dir("https://open.spotify.com/playlist/other", settings)
    other.mkdir(parents=True)
    (other / "previewed.mp3").write_bytes(b"\x00")
    (tmp_path / "legacy-root.mp3").write_bytes(b"\x00")

    sampled: list = []
    real = backends.staging_files

    def spy(directory):
        result = real(directory)
        sampled.append(directory)
        return result

    monkeypatch.setattr(backends, "staging_files", spy)

    def runner(_url, _settings, _store, *, on_update=None):
        deadline = time.time() + 5
        while len(sampled) < 2 and time.time() < deadline:  # >=1 full monitor tick
            time.sleep(0.01)
        return "spotdl", []

    job = _inline().start(url, settings, runner=runner)
    assert sampled and all(directory == mine for directory in sampled)
    assert job.downloaded == 2  # own staging only


def test_crate_with_pending_preview_is_forced_back_into_preview(tmp_path):
    # Adversarial: the crates-page Re-run carries no "move my files" intent,
    # and a re-sort recomputes destinations the user never saw — so any crate
    # holding previewed rows previews again. Apply is the one move mechanism.
    db = tmp_path / "j.db"
    seed = CrateStore(db)
    seed.upsert_track("u", Track(spotify_id="1", title="x", artist="y", status="previewed"))
    seed.close()
    captured: dict = {}
    manager = JobManager(store_factory=lambda: CrateStore(db), spawn=lambda work: work())
    manager.start("u", Settings(), runner=_capture_dry_run(captured))
    assert captured["dry_run"] is True


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
