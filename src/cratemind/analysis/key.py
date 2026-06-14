"""Estimate a track's musical key and express it in Camelot notation (8A, 11B…)
for harmonic mixing.

The pure scoring (`camelot_from_chroma`) uses the Krumhansl-Schmuckler key
profiles and is unit-tested without librosa. `estimate_camelot` wraps librosa's
chroma for real audio.
"""

from __future__ import annotations

from pathlib import Path

# Krumhansl-Schmuckler key profiles (index 0 = tonic).
_MAJOR = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
_MINOR = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)

# Pitch class (C=0 … B=11) -> Camelot code.
CAMELOT_MAJOR = {0: "8B", 1: "3B", 2: "10B", 3: "5B", 4: "12B", 5: "7B",
                 6: "2B", 7: "9B", 8: "4B", 9: "11B", 10: "6B", 11: "1B"}
CAMELOT_MINOR = {0: "5A", 1: "12A", 2: "7A", 3: "2A", 4: "9A", 5: "4A",
                 6: "11A", 7: "6A", 8: "1A", 9: "8A", 10: "3A", 11: "10A"}


def _corr(a: list[float], b: tuple[float, ...]) -> float:
    n = len(a)
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    num = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    den_a = sum((x - mean_a) ** 2 for x in a) ** 0.5
    den_b = sum((x - mean_b) ** 2 for x in b) ** 0.5
    return num / (den_a * den_b) if den_a and den_b else 0.0


def camelot_from_chroma(chroma: list[float] | tuple[float, ...]) -> str:
    """Pick the best-fitting key for a 12-bin chroma vector, as a Camelot code.

    Returns "" for silence (an all-zero chroma).
    """
    vec = [float(v) for v in chroma]
    total = sum(vec)
    if total <= 0:
        return ""
    vec = [v / total for v in vec]
    best_tonic, best_mode, best_corr = 0, "maj", float("-inf")
    for tonic in range(12):
        rotated = vec[tonic:] + vec[:tonic]  # align candidate tonic to index 0
        for mode, profile in (("maj", _MAJOR), ("min", _MINOR)):
            score = _corr(rotated, profile)
            if score > best_corr:
                best_tonic, best_mode, best_corr = tonic, mode, score
    return CAMELOT_MAJOR[best_tonic] if best_mode == "maj" else CAMELOT_MINOR[best_tonic]


def estimate_camelot(audio_path: Path) -> str:
    """Estimate the Camelot key of an audio file via librosa (lazy import)."""
    import librosa  # noqa: PLC0415

    y, sr = librosa.load(str(audio_path), mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    return camelot_from_chroma(chroma.mean(axis=1).tolist())
