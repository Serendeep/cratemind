from starlette.testclient import TestClient

from cratemind.download.base import Track
from cratemind.web import app as appmod
from cratemind.web.jobs import Job, JobManager
from cratemind.web.view import PAGE_SIZE, paginate

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
