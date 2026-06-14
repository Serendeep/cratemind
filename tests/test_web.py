from starlette.testclient import TestClient

from cratemind.download.base import Track
from cratemind.web import app as appmod
from cratemind.web.jobs import Job, JobManager

client = TestClient(appmod.app)


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
