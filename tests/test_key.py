from cratemind.analysis.key import camelot_from_chroma


def _chroma(peaks: dict[int, float]) -> list[float]:
    vec = [0.0] * 12
    for pitch_class, weight in peaks.items():
        vec[pitch_class] = weight
    return vec


def test_c_major_maps_to_8b():
    # C, E, G prominent -> C major -> 8B
    assert camelot_from_chroma(_chroma({0: 1.0, 4: 0.8, 7: 0.9})) == "8B"


def test_a_minor_maps_to_8a():
    # A, C, E prominent -> A minor -> 8A
    assert camelot_from_chroma(_chroma({9: 1.0, 0: 0.8, 4: 0.9})) == "8A"


def test_silence_returns_empty():
    assert camelot_from_chroma([0.0] * 12) == ""
