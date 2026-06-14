from pathlib import Path

import pytest

from cratemind.download import backends, tags
from cratemind.download.backends import (
    BackendUnavailable,
    SpotdlBackend,
    SpotiFlacBackend,
    build_spotdl_command,
    build_spotiflac_command,
    fetch_playlist,
    select_backends,
)
from cratemind.config import Settings

URL = "https://open.spotify.com/playlist/abc"


def test_select_backends_flac_prefers_lossless_then_fallback():
    chosen = select_backends("flac")
    assert [b.name for b in chosen] == ["spotiflac", "spotdl"]


def test_select_backends_lossy_is_spotdl_only():
    assert [b.name for b in select_backends("mp3")] == ["spotdl"]


def test_spotiflac_supports_only_flac():
    b = SpotiFlacBackend()
    assert b.supports("flac") and not b.supports("mp3")


def test_build_spotdl_command_shape():
    cmd = build_spotdl_command(URL, Path("/out"), "mp3")
    assert cmd[:3] == ["spotdl", "download", URL]
    assert "--format" in cmd and "mp3" in cmd
    assert "--output" in cmd and "/out" in cmd


def test_build_spotiflac_command_is_positional():
    # SpotiFLAC CLI: `spotiflac <url> <output_dir>`
    assert build_spotiflac_command(URL, Path("/out")) == ["spotiflac", URL, "/out"]


def test_is_lossless_by_suffix():
    assert tags.is_lossless(Path("a.flac"))
    assert not tags.is_lossless(Path("a.mp3"))


def test_stable_id_is_deterministic():
    assert tags.stable_id("Kavinsky", "Nightcall") == tags.stable_id("Kavinsky", "Nightcall")
    assert tags.stable_id("A", "B") != tags.stable_id("B", "A")


def test_track_from_file_maps_and_canonicalizes_genre(monkeypatch):
    monkeypatch.setattr(
        tags,
        "read_tags",
        lambda _p: {"title": "Nightcall", "artist": "Kavinsky", "genre": "Drum & Bass"},
    )
    track = tags.track_from_file(Path("/m/nightcall.flac"), source="spotiflac")
    assert track.title == "Nightcall"
    assert track.genre == "drum and bass"  # canonicalized
    assert track.lossless is True
    assert track.source == "spotiflac"
    assert track.status == "downloading"


def test_missing_cli_raises_backend_unavailable(monkeypatch):
    monkeypatch.setattr(backends.shutil, "which", lambda _name: None)
    with pytest.raises(BackendUnavailable):
        SpotdlBackend("mp3").fetch(URL, Path("/tmp/cm-nope"))


def test_fetch_playlist_falls_through_to_spotdl(monkeypatch, tmp_path):
    settings = Settings(output_dir=tmp_path, audio_format="flac")
    created = tmp_path / "song.mp3"

    def fake_run(command):
        # SpotiFLAC missing -> unavailable; spotdl "downloads" a file
        if command[0] == "spotiflac":
            raise BackendUnavailable("spotiflac missing")
        created.write_bytes(b"\x00")

    monkeypatch.setattr(backends, "_run", fake_run)
    monkeypatch.setattr(tags, "read_tags", lambda _p: {"title": "Song", "artist": "X", "genre": None})

    name, tracks = fetch_playlist(URL, settings)
    assert name == "spotdl"
    assert len(tracks) == 1 and tracks[0].source == "spotdl"
