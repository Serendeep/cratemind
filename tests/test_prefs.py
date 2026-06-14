from starlette.testclient import TestClient

from cratemind import prefs
from cratemind.config import Settings
from cratemind.web import app as appmod
from cratemind.web.jobs import JobManager

client = TestClient(appmod.app)


def test_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("CRATEMIND_DATA_DIR", str(tmp_path))
    prefs.save_settings(
        Settings(output_dir=tmp_path / "music", audio_format="mp3", bucket_width=10)
    )
    loaded = prefs.load_settings()
    assert loaded.output_dir == tmp_path / "music"
    assert loaded.audio_format == "mp3"
    assert loaded.bucket_width == 10


def test_missing_prefs_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("CRATEMIND_DATA_DIR", str(tmp_path))
    assert prefs.load_settings().audio_format == "flac"


def test_corrupt_prefs_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("CRATEMIND_DATA_DIR", str(tmp_path))
    (tmp_path / "prefs.json").write_text("{ broken json")
    assert prefs.load_settings().audio_format == "flac"


def test_run_remembers_settings_in_the_form(tmp_path, monkeypatch):
    monkeypatch.setenv("CRATEMIND_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(appmod, "jobs", JobManager(spawn=lambda work: work()))
    target = str(tmp_path / "crate")
    _ = client.post(
        "/runs",
        data={
            "playlist_url": "https://open.spotify.com/playlist/x",
            "output_dir": target,
            "audio_format": "mp3",
        },
    )
    page = client.get("/").text
    assert target in page  # output folder pre-filled
    assert 'value="mp3" selected' in page  # format remembered
