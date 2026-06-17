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


def test_predict_requests_only_the_class_head(monkeypatch):
    """Only the logits output is requested, so onnxruntime doesn't materialize
    the 12 unused per-layer token outputs (each emits a shape-mismatch warning)."""
    import pytest

    np = pytest.importorskip("numpy")  # _predict needs the optional audio stack

    captured = {}

    class _Input:
        name = "melspectrogram"

    class FakeSession:
        def get_inputs(self):
            return [_Input()]

        def run(self, output_names, feeds):
            captured["output_names"] = output_names
            return [np.zeros((2, 3), dtype=np.float32)]

    monkeypatch.setattr(audio, "_patches", lambda _p: np.zeros((2, 626, 96), dtype=np.float32))
    monkeypatch.setattr(audio, "_session", lambda: FakeSession())
    monkeypatch.setattr(audio, "_labels", lambda: ["a", "b", "c"])

    result = audio._predict(Path("/x.flac"))
    assert result is not None
    assert captured["output_names"] == ["logits"]
