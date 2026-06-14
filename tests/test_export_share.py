from starlette.testclient import TestClient

from cratemind.download.base import Track
from cratemind.web import app as appmod
from cratemind.web.jobs import Job

client = TestClient(appmod.app)


def _seed_job(job_id: str) -> Job:
    job = Job(
        id=job_id,
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
    appmod.jobs._jobs[job_id] = job  # type: ignore[attr-defined]
    return job


def test_export_returns_crate_json_attachment():
    _seed_job("exp1")
    response = client.get("/runs/exp1/export")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    assert "Nightcall" in response.text
    assert "112-119" in response.text


def test_export_unknown_job_404():
    assert client.get("/runs/missing/export").status_code == 404


def test_share_returns_copyable_link(monkeypatch):
    _seed_job("exp2")
    monkeypatch.setattr(appmod, "share_crate", lambda _path: "https://files.catbox.moe/abc.json")
    response = client.post("/runs/exp2/share")
    assert response.status_code == 200
    assert "https://files.catbox.moe/abc.json" in response.text
    assert "Copy" in response.text


def test_share_failure_renders_error(monkeypatch):
    _seed_job("exp3")

    def boom(_path):
        raise RuntimeError("both hosts down")

    monkeypatch.setattr(appmod, "share_crate", boom)
    response = client.post("/runs/exp3/share")
    assert "Share failed" in response.text
