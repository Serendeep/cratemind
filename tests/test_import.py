from starlette.testclient import TestClient

from cratemind.config import Settings
from cratemind.download.base import Track
from cratemind.manifest import CrateManifest, TrackEntry
from cratemind.pipeline import place_from_manifest
from cratemind.runner import run_crate
from cratemind.store.db import CrateStore
from cratemind.web import app as appmod
from cratemind.web.jobs import JobManager

client = TestClient(appmod.app)
PLAYLIST = "https://open.spotify.com/playlist/x"


def test_place_from_manifest_files_using_manifest_values(tmp_path):
    out = tmp_path / "out"
    src = tmp_path / "song.flac"
    src.write_bytes(b"\x00")
    track = Track(spotify_id="1", title="Nightcall", artist="Kavinsky", file_path=src)
    result = place_from_manifest(
        track, Settings(output_dir=out), bpm=118, bpm_bucket="112-119", genre="synthwave"
    )
    assert result.status == "sorted"
    assert result.bpm == 118
    assert result.genre == "synthwave"
    assert result.file_path == out / "synthwave" / "112-119" / "song.flac"
    assert result.file_path.exists()


def test_runner_overrides_skip_analysis(tmp_path):
    out = tmp_path / "out"
    src = tmp_path / "a.flac"
    src.write_bytes(b"\x00")
    store = CrateStore()
    track = Track(spotify_id="abc", title="x", artist="y", file_path=src)
    called: list[str] = []

    def fetch(_url, _settings):
        return "spotdl", [track]

    def process(t, _settings):
        called.append(t.spotify_id)
        return t.update(status="sorted")

    overrides = {
        "abc": TrackEntry(
            spotify_id="abc", title="x", artist="y", genre="house", bpm=124, bpm_bucket="120-127"
        )
    }
    _name, results = run_crate(
        PLAYLIST, Settings(output_dir=out), store, fetch=fetch, process=process, overrides=overrides
    )
    assert called == []  # analysis skipped — used the manifest
    assert results[0].bpm == 124
    assert results[0].genre == "house"
    assert results[0].file_path == out / "house" / "120-127" / "a.flac"


def test_import_route_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(appmod, "jobs", JobManager(spawn=lambda work: work()))
    response = client.post(
        "/import",
        files={"crate": ("crate.json", b"{not json}", "application/json")},
        data={"output_dir": "/tmp/cm"},
    )
    assert response.status_code == 400
    assert "valid crate.json" in response.text


def test_import_route_starts_a_job(monkeypatch):
    monkeypatch.setattr(appmod, "jobs", JobManager(spawn=lambda work: work()))
    manifest = CrateManifest(
        playlist_url=PLAYLIST,
        tracks=[TrackEntry(spotify_id="1", title="t", artist="a", genre="house", bpm=124)],
    )
    response = client.post(
        "/import",
        files={"crate": ("crate.json", manifest.to_json().encode(), "application/json")},
        data={"output_dir": "/tmp/cm"},
    )
    assert response.status_code == 200
    assert "Couldn't run" in response.text  # no spotdl installed in CI -> error partial
