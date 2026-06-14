from pathlib import Path

from cratemind.analysis.analyzer import analyze_bpm
from cratemind.config import Settings
from cratemind.download.base import Track
from cratemind.genre.resolve import resolve_genre


def _track(**overrides) -> Track:
    base = {"spotify_id": "1", "title": "T", "artist": "A", "file_path": Path("/x.flac")}
    base.update(overrides)
    return Track(**base)  # type: ignore[arg-type]


def test_analyze_folds_octave_and_assigns_bucket():
    settings = Settings(octave_low=70, octave_high=180, bucket_width=8)
    track = analyze_bpm(_track(), settings, estimator=lambda _p: 64.0)
    assert track.bpm == 128  # 64 folded up into the window
    assert track.bpm_bucket == "128-135"
    assert track.status == "analyzing"


def test_analyze_without_file_marks_failed():
    track = analyze_bpm(_track(file_path=None), Settings(), estimator=lambda _p: 120.0)
    assert track.status == "failed"


def test_resolve_genre_prefers_tag():
    assert resolve_genre(_track(genre="Drum & Bass")) == "drum and bass"


def test_resolve_genre_falls_back_to_artist_lookup():
    track = _track(genre=None, artist="Kavinsky")
    assert resolve_genre(track, artist_genre_lookup=lambda _a: "Synthwave") == "synthwave"


def test_resolve_genre_returns_none_when_nothing_found():
    assert resolve_genre(_track(genre=None)) is None
