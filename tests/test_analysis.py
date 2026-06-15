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


def test_resolve_genre_prefers_audio_over_coarse_and_artist():
    # Audio gives the specific sub-genre; it must win over the coarse Deezer net.
    track = _track(genre=None, artist="T78", file_path=Path("/x.flac"))
    genre = resolve_genre(
        track,
        audio_genre_lookup=lambda _p: "Hard Techno",
        coarse_genre_lookup=lambda _a, _t: "electronic",
    )
    assert genre == "hard techno"


def test_resolve_genre_uses_coarse_when_audio_blank():
    track = _track(genre=None, artist="T78", file_path=Path("/x.flac"))
    genre = resolve_genre(
        track,
        audio_genre_lookup=lambda _p: None,
        coarse_genre_lookup=lambda _a, _t: "electronic",
    )
    assert genre == "electronic"


def test_resolve_genre_falls_back_to_artist_name_when_nothing_found():
    # User decision: group by artist instead of dumping into `unsorted`.
    assert resolve_genre(_track(genre=None, artist="T78")) == "T78"


def test_resolve_genre_is_none_only_without_artist():
    assert resolve_genre(_track(genre=None, artist="")) is None
