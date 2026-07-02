from pathlib import Path

from starlette.testclient import TestClient

from cratemind.download.base import Track
from cratemind.web import app as appmod
from cratemind.web.jobs import Job, JobManager
from cratemind.web.view import PAGE_SIZE, art_ids, folder_tree, paginate, summarize

client = TestClient(appmod.app)


def _sorted_tracks(count: int) -> list[Track]:
    return [
        Track(spotify_id=str(i), title=f"T{i:02d}", artist=f"A{i:02d}", status="sorted")
        for i in range(count)
    ]


def test_paginate_slices_and_reports_totals():
    page = paginate(_sorted_tracks(20), page=1)
    assert len(page.tracks) == PAGE_SIZE
    assert page.number == 1 and page.total == 2
    second = paginate(_sorted_tracks(20), page=2)
    assert len(second.tracks) == 20 - PAGE_SIZE
    assert second.number == 2


def test_paginate_clamps_out_of_range_page():
    # A stale page number (e.g. the list shrank under the auto-poll) clamps in.
    page = paginate(_sorted_tracks(3), page=9)
    assert page.number == 1 and page.total == 1
    assert len(page.tracks) == 3


def test_paginate_empty_is_page_one_of_one():
    page = paginate([], page=1)
    assert page.tracks == [] and page.number == 1 and page.total == 1


def test_poll_shows_determinate_download_progress_when_total_known():
    # No tracks yet, but spotdl's tracklist gave a total -> "N / TOTAL" + real bar.
    job = Job(id="dl1", playlist_url="u", status="running", downloaded=3, total_expected=10)
    appmod.jobs._jobs["dl1"] = job  # type: ignore[attr-defined]
    text = client.get("/runs/dl1").text
    assert "3</b> / 10 tracks" in text
    assert "width:30%" in text
    assert "indet" not in text  # determinate bar, not the spinner


def test_poll_falls_back_to_indeterminate_when_total_unknown():
    # SpotiFLAC (or pre-tracklist) -> total 0 -> indeterminate spinner.
    job = Job(id="dl2", playlist_url="u", status="running", downloaded=2, total_expected=0)
    appmod.jobs._jobs["dl2"] = job  # type: ignore[attr-defined]
    text = client.get("/runs/dl2").text
    assert "2</b> tracks ready" in text
    assert "prog indet" in text


def test_poll_renders_requested_page_with_controls():
    job = Job(id="pg1", playlist_url="u", status="done", tracks=_sorted_tracks(20))
    appmod.jobs._jobs["pg1"] = job  # type: ignore[attr-defined]
    page2 = client.get("/runs/pg1?page=2")
    assert page2.status_code == 200
    assert "page 2 of 2" in page2.text
    assert "T15" in page2.text and "T00" not in page2.text  # second page only
    page1 = client.get("/runs/pg1")  # defaults to page 1
    assert "page 1 of 2" in page1.text
    assert "T00" in page1.text and "T15" not in page1.text


def test_index_renders_form_and_favicon():
    response = client.get("/")
    assert response.status_code == 200
    assert "cratemind" in response.text
    assert 'name="playlist_url"' in response.text
    assert 'name="online_genre"' in response.text  # the opt-in Deezer toggle
    assert "favicon.svg" in response.text
    assert "<main" in response.text and "<footer" in response.text  # semantic, sticky footer


def test_health_ok():
    assert client.get("/health").json() == {"status": "ok"}


def test_favicon_is_svg_with_brand_dot():
    response = client.get("/favicon.svg")
    assert response.status_code == 200
    assert "svg" in response.headers["content-type"]
    assert "#7fb98a" in response.text  # the green accent dot


def test_poll_unknown_run_is_404():
    assert client.get("/runs/does-not-exist").status_code == 404


def test_crates_page_lists_past_runs(tmp_path, monkeypatch):
    from cratemind.store.db import CrateStore

    db = tmp_path / "c.db"
    monkeypatch.setattr(appmod, "open_store", lambda: CrateStore(db))
    url = "https://open.spotify.com/playlist/x"
    seed = CrateStore(db)
    seed.upsert_run(url, name="Alien Perception")
    seed.upsert_track(url, Track(spotify_id="1", title="T", artist="A", status="sorted"))
    seed.close()

    response = client.get("/crates")
    assert response.status_code == 200
    assert "Alien Perception" in response.text
    assert "1 sorted" in response.text


def test_settings_lists_default_and_custom_aliases(tmp_path, monkeypatch):
    from cratemind.store.db import CrateStore

    db = tmp_path / "s.db"
    monkeypatch.setattr(appmod, "open_store", lambda: CrateStore(db))
    seed = CrateStore(db)
    seed.set_alias("techno", "warehouse")
    seed.close()

    text = client.get("/settings").text
    assert "warehouse" in text  # the custom alias
    assert "drum and bass" in text  # a built-in default alias shown read-only


def test_add_alias_normalizes_and_persists(tmp_path, monkeypatch):
    from cratemind.store.db import CrateStore

    db = tmp_path / "s.db"
    monkeypatch.setattr(appmod, "open_store", lambda: CrateStore(db))
    # "Hard Techno" / "Warehouse" -> normalized lowercase keys/values.
    r = client.post("/settings/alias", data={"name": "Hard Techno", "canonical": "Warehouse"})
    assert r.status_code in (200, 303)
    store = CrateStore(db)
    assert store.aliases() == {"hard techno": "warehouse"}
    store.close()


def test_delete_alias_removes_it(tmp_path, monkeypatch):
    from cratemind.store.db import CrateStore

    db = tmp_path / "s.db"
    monkeypatch.setattr(appmod, "open_store", lambda: CrateStore(db))
    seed = CrateStore(db)
    seed.set_alias("dnb", "drum and bass")
    seed.close()

    r = client.post("/settings/alias/delete", data={"name": "dnb"})
    assert r.status_code in (200, 303)
    store = CrateStore(db)
    assert store.aliases() == {}
    store.close()


def test_delete_alias_normalizes_name_like_add(tmp_path, monkeypatch):
    from cratemind.store.db import CrateStore

    db = tmp_path / "s.db"
    monkeypatch.setattr(appmod, "open_store", lambda: CrateStore(db))
    seed = CrateStore(db)
    seed.set_alias("drum and bass", "dnb")  # stored under the normalized key
    seed.close()

    # Posting a non-normalized name must still delete the normalized entry.
    client.post("/settings/alias/delete", data={"name": "Drum & Bass"})
    store = CrateStore(db)
    assert store.aliases() == {}
    store.close()


def test_export_stored_crate_from_disk(tmp_path, monkeypatch):
    from cratemind.store.db import CrateStore, run_id_for

    db = tmp_path / "c.db"
    monkeypatch.setattr(appmod, "open_store", lambda: CrateStore(db))
    url = "https://open.spotify.com/playlist/x"
    seed = CrateStore(db)
    seed.upsert_run(url, name="X")
    seed.upsert_track(
        url, Track(spotify_id="1", title="T", artist="A", genre="techno", status="sorted")
    )
    seed.close()

    response = client.get(f"/crates/{run_id_for(url)}/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "techno" in response.text  # the stored analysis, exported with no live job


def test_export_unknown_crate_is_404(tmp_path, monkeypatch):
    from cratemind.store.db import CrateStore

    monkeypatch.setattr(appmod, "open_store", lambda: CrateStore(tmp_path / "c.db"))
    assert client.get("/crates/deadbeef0000/export").status_code == 404


def test_run_without_backend_shows_error(monkeypatch):
    # inline manager runs the job synchronously; no spotdl -> error partial
    monkeypatch.setattr(appmod, "jobs", JobManager(spawn=lambda work: work()))
    response = client.post(
        "/runs",
        data={"playlist_url": "https://open.spotify.com/playlist/x", "output_dir": "/tmp/cm"},
    )
    assert response.status_code == 200
    assert "Couldn't run" in response.text


def test_poll_renders_summary_for_finished_job():
    job = Job(
        id="abc123",
        playlist_url="https://open.spotify.com/playlist/x",
        status="done",
        backend="spotiflac",
        tracks=[
            Track(
                spotify_id="1",
                title="Nightcall",
                artist="Kavinsky",
                genre="synthwave",
                bpm=118,
                bpm_bucket="112-119",
                source="spotiflac",
                lossless=True,
                status="sorted",
            )
        ],
    )
    appmod.jobs._jobs["abc123"] = job  # type: ignore[attr-defined]
    response = client.get("/runs/abc123")
    assert response.status_code == 200
    assert "Nightcall" in response.text
    assert "112-119" in response.text
    assert "crate summary" in response.text
    assert "100%" in response.text  # 1/1 lossless
    assert ">lossless<" in response.text  # stat shown when a lossless track exists


def _previewed_track(i: int, genre: str = "techno") -> Track:
    return Track(
        spotify_id=str(i), title=f"T{i}", artist=f"A{i}", genre=genre,
        genre_confidence=0.8, bpm=140, bpm_bucket="136-143",
        file_path=Path(f"/staging/{i}.flac"),
        proposed_path=Path(f"/music/{genre}/136-143/{i}.flac"),
        status="previewed",
    )


def test_summarize_counts_previewed_as_progress():
    tracks = [_previewed_track(1), _previewed_track(2).update(status="sorted")]
    summary = summarize(tracks)
    assert summary["previewed"] == 1
    assert summary["progress_pct"] == 100  # analysis done for both
    # Regression: with no previewed tracks the numbers are the old ones.
    plain = summarize([_previewed_track(1).update(status="sorted", proposed_path=None)])
    assert plain["previewed"] == 0 and plain["progress_pct"] == 100


def test_folder_tree_groups_by_proposed_folder_relative_to_root():
    tracks = [
        _previewed_track(1, genre="techno"),
        _previewed_track(2, genre="techno"),
        _previewed_track(3, genre="house"),
        _previewed_track(4).update(status="sorted"),  # sorted rows stay out
    ]
    tree = folder_tree(tracks, Path("/music"))
    assert [(label, len(items)) for label, items in tree] == [
        ("house/136-143", 1),
        ("techno/136-143", 2),
    ]


def test_folder_tree_falls_back_to_absolute_outside_root():
    tree = folder_tree([_previewed_track(1)], Path("/elsewhere"))
    assert tree[0][0] == "/music/techno/136-143"


def test_art_ids_uses_the_reader_per_file():
    tracks = [_previewed_track(1), _previewed_track(2)]
    ids = art_ids(tracks, reader=lambda p: "1" in p.name)
    assert ids == {"1"}


def test_preview_run_renders_apply_button_destination_and_tree():
    job = Job(
        id="prev1", playlist_url="u", status="done", backend="spotdl",
        output_dir=Path("/music"), tracks=[_previewed_track(1)],
    )
    appmod.jobs._jobs["prev1"] = job  # type: ignore[attr-defined]
    text = client.get("/runs/prev1").text
    assert "previewed" in text
    assert "Apply — move 1 track" in text
    assert "/music/techno/136-143" in text  # destination column
    assert "proposed structure" in text  # the folder tree
    assert "80%" in text  # genre confidence rendered
    assert ">destination<" in text and ">source<" not in text


def test_sorted_run_keeps_the_source_column_and_no_apply():
    job = Job(
        id="plain1", playlist_url="u", status="done", backend="spotdl",
        tracks=[Track(spotify_id="1", title="x", artist="y", genre="techno",
                      source="spotdl", status="sorted")],
    )
    appmod.jobs._jobs["plain1"] = job  # type: ignore[attr-defined]
    text = client.get("/runs/plain1").text
    assert ">source<" in text
    assert "Apply — move" not in text
    assert "proposed structure" not in text
    assert 'class="art"' not in text  # no art anywhere → column absent entirely


def test_index_has_the_preview_checkbox():
    text = client.get("/").text
    assert 'name="dry_run"' in text
    assert "preview first" in text


def test_run_form_passes_dry_run_to_settings(monkeypatch):
    seen = {}

    class StubJobs:
        def start(self, url, settings, **kwargs):
            seen["dry_run"] = settings.dry_run
            return Job(id="stub", playlist_url=url, status="done")

        def get(self, _id):
            return None

    monkeypatch.setattr(appmod, "jobs", StubJobs())
    client.post(
        "/runs",
        data={"playlist_url": "u", "output_dir": "/tmp/cm", "dry_run": "true"},
    )
    assert seen["dry_run"] is True
    client.post("/runs", data={"playlist_url": "u", "output_dir": "/tmp/cm"})
    assert seen["dry_run"] is False


def test_apply_route_starts_an_apply_job(monkeypatch):
    calls = {}

    def fake_apply_crate(url, settings, store, *, on_update=None):
        calls["url"] = url
        return "apply", []

    monkeypatch.setattr(appmod, "apply_crate", fake_apply_crate)
    manager = JobManager(spawn=lambda work: work())
    monkeypatch.setattr(appmod, "jobs", manager)
    source = manager.start("u", appmod.Settings(), runner=lambda *a, **k: ("spotdl", []))
    response = client.post(f"/runs/{source.id}/apply")
    assert response.status_code == 200
    assert calls["url"] == "u"


def test_apply_route_unknown_job_is_404():
    assert client.post("/runs/nope/apply").status_code == 404


def test_art_route_serves_embedded_art(monkeypatch):
    job = Job(id="art1", playlist_url="u", status="done", tracks=[_previewed_track(1)])
    appmod.jobs._jobs["art1"] = job  # type: ignore[attr-defined]
    monkeypatch.setattr(appmod, "read_art", lambda _p: (b"imgbytes", "image/jpeg"))
    response = client.get("/runs/art1/art/1")
    assert response.status_code == 200
    assert response.content == b"imgbytes"
    assert response.headers["content-type"] == "image/jpeg"
    assert "max-age" in response.headers["cache-control"]


def test_art_route_missing_art_and_unknown_ids_are_404(monkeypatch):
    job = Job(id="art2", playlist_url="u", status="done", tracks=[_previewed_track(1)])
    appmod.jobs._jobs["art2"] = job  # type: ignore[attr-defined]
    monkeypatch.setattr(appmod, "read_art", lambda _p: None)
    assert client.get("/runs/art2/art/1").status_code == 404  # file has no art
    assert client.get("/runs/art2/art/99").status_code == 404  # unknown track
    assert client.get("/runs/nope/art/1").status_code == 404  # unknown job


def test_preview_then_apply_end_to_end(tmp_path, monkeypatch):
    # The whole trust loop through real routes, runner, sorter, and disk:
    # preview moves nothing; Apply moves exactly what was shown; a double
    # Apply changes nothing and fails nothing.
    from cratemind.organize.sorter import sort_track

    monkeypatch.setenv("CRATEMIND_DATA_DIR", str(tmp_path))  # isolated store+prefs
    src = tmp_path / "incoming" / "a.flac"
    src.parent.mkdir()
    src.write_bytes(b"\x00")
    out = tmp_path / "out"
    fetched = Track(
        spotify_id="1", title="x", artist="y", genre="techno",
        file_path=src, status="downloading",
    )

    def fake_process(track, settings):  # analysis faked, sorting real
        return sort_track(track.update(bpm=140, bpm_bucket="136-143"), settings)

    class InjectingManager(JobManager):
        def start(self, url, settings, **kw):  # type: ignore[override]
            if "runner" not in kw:  # the download runner needs a fake fetch
                kw["runner_kwargs"] = {
                    "fetch": lambda _u, _s: ("spotdl", [fetched]),
                    "process": fake_process,
                }
            return super().start(url, settings, **kw)

    manager = InjectingManager(spawn=lambda work: work())
    monkeypatch.setattr(appmod, "jobs", manager)

    previewed = client.post(
        "/runs",
        data={
            "playlist_url": "https://open.spotify.com/playlist/e2e",
            "output_dir": str(out),
            "dry_run": "true",
        },
    ).text
    assert "previewed" in previewed and "Apply — move 1 track" in previewed
    assert src.exists() and not (out / "techno").exists()  # nothing moved

    job_id = next(iter(manager._jobs))  # the preview job
    applied = client.post(f"/runs/{job_id}/apply").text
    dest = out / "techno" / "136-143" / "a.flac"
    assert dest.exists() and not src.exists()  # moved exactly as shown
    assert 'st sorted' in applied and 'st failed' not in applied  # status cells

    apply_job_id = appmod._state["active"]
    again = client.post(f"/runs/{apply_job_id}/apply").text  # double click
    assert dest.exists()
    assert not (out / "techno" / "136-143" / "a (1).flac").exists()
    assert 'st failed' not in again  # idempotent, no corrupted rows


def test_summary_hides_lossless_stat_for_spotdl_only_run():
    # spotdl is always lossy, so the lossless stat would read a flat 0% — hide it.
    job = Job(
        id="lossy1",
        playlist_url="u",
        status="done",
        backend="spotdl",
        tracks=[
            Track(spotify_id="1", title="x", artist="y", genre="techno",
                  bpm=140, bpm_bucket="136-143", source="spotdl",
                  lossless=False, status="sorted"),
        ],
    )
    appmod.jobs._jobs["lossy1"] = job  # type: ignore[attr-defined]
    response = client.get("/runs/lossy1")
    assert response.status_code == 200
    assert "crate summary" in response.text
    assert ">lossless<" not in response.text  # stat hidden, no flat 0%
