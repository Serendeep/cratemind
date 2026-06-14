from pathlib import Path

from cratemind.config import Settings
from cratemind.download.base import Track
from cratemind.organize.sorter import sort_track
from cratemind.pipeline import process_track


def _make_file(tmp_path: Path, name: str = "song.flac") -> Path:
    path = tmp_path / name
    path.write_bytes(b"\x00")
    return path


def test_sort_track_moves_into_genre_bucket(tmp_path):
    out = tmp_path / "out"
    src = _make_file(tmp_path)
    track = Track(
        spotify_id="1",
        title="Nightcall",
        artist="Kavinsky",
        genre="synthwave",
        bpm=118,
        bpm_bucket="112-119",
        file_path=src,
    )
    result = sort_track(track, Settings(output_dir=out))
    assert result.status == "sorted"
    assert result.file_path == out / "synthwave" / "112-119" / "song.flac"
    assert result.file_path.exists()
    assert src.exists()  # cached original kept so reruns skip the download


def test_sort_track_uses_unsorted_without_genre(tmp_path):
    out = tmp_path / "out"
    src = _make_file(tmp_path)
    track = Track(
        spotify_id="1",
        title="x",
        artist="y",
        genre=None,
        bpm=96,
        bpm_bucket="96-103",
        file_path=src,
    )
    result = sort_track(track, Settings(output_dir=out))
    assert result.file_path == out / "unsorted" / "96-103" / "song.flac"


def test_name_collision_gets_suffix(tmp_path):
    out = tmp_path / "out"
    settings = Settings(output_dir=out)
    common = {"genre": "house", "bpm": 124, "bpm_bucket": "120-127"}
    first = Track(spotify_id="1", title="x", artist="y", file_path=_make_file(tmp_path, "a.flac"), **common)
    sort_track(first, settings)
    second = Track(spotify_id="2", title="x", artist="y", file_path=_make_file(tmp_path, "a.flac"), **common)
    result = sort_track(second, settings)
    assert result.file_path.name == "a (1).flac"


def test_process_track_end_to_end(tmp_path):
    out = tmp_path / "out"
    src = _make_file(tmp_path, "track.flac")
    track = Track(spotify_id="1", title="Resonance", artist="HOME", genre="chillwave", file_path=src)
    result = process_track(track, Settings(output_dir=out), estimator=lambda _p: 110.0)
    assert result.status == "sorted"
    assert result.bpm == 110
    assert result.file_path == out / "chillwave" / "104-111" / "track.flac"
    assert result.file_path.exists()
