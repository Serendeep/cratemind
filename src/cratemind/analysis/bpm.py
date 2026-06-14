"""BPM helpers.

The octave-fold and bucketing logic is pure and unit-tested here. The actual
tempo estimation (`estimate_raw_bpm`) wraps librosa and is imported lazily so
the rest of the app — and these tests — don't need the heavy audio stack.
"""

from __future__ import annotations

from pathlib import Path


def fold_octave(bpm: float, low: int, high: int) -> int:
    """Fold a tempo into [low, high] by doubling/halving, then round.

    librosa's beat tracker often locks onto half or double the true tempo.
    Folding into a plausible window resolves the common octave error so a
    124-BPM house track never files itself under 62.
    """
    if bpm <= 0:
        raise ValueError("bpm must be positive")
    if high < low * 2:
        raise ValueError("octave window must span at least one octave (high >= 2*low)")
    value = float(bpm)
    while value < low:
        value *= 2
    while value > high:
        value /= 2
    return round(value)


def bucket(bpm: int, width: int) -> str:
    """Name the fixed-width band a tempo falls in, e.g. bucket(105, 8) -> '104-111'."""
    if width <= 0:
        raise ValueError("width must be positive")
    start = (bpm // width) * width
    end = start + width - 1
    return f"{start}-{end}"


def estimate_raw_bpm(audio_path: Path) -> float:
    """Estimate uncorrected tempo from an audio file via librosa (lazy import)."""
    import librosa  # noqa: PLC0415 — deferred so core/tests skip the heavy dep
    import numpy as np

    y, sr = librosa.load(str(audio_path), mono=True)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    # librosa >= 0.10 returns tempo as an ndarray; pull the scalar safely.
    return float(np.atleast_1d(tempo)[0])
