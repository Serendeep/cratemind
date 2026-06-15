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
