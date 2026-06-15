from pathlib import Path

from cratemind.genre import audio


def test_clean_label_strips_family_prefix():
    assert audio._clean_label("Electronic---Hard Techno") == "Hard Techno"
    assert audio._clean_label("Techno") == "Techno"


def test_lookup_returns_none_when_model_unavailable(monkeypatch):
    monkeypatch.setattr(audio, "is_available", lambda: False)
    assert audio.lookup_audio_genre(Path("/nope.flac")) is None


def test_lookup_swallows_errors(monkeypatch):
    monkeypatch.setattr(audio, "is_available", lambda: True)

    def boom(_path):
        raise RuntimeError("model failure")

    monkeypatch.setattr(audio, "_predict", boom)
    assert audio.lookup_audio_genre(Path("/x.flac")) is None
