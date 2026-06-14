"""Turn a downloaded Track into an analyzed one: detect BPM, fold the octave,
assign a bucket. The tempo estimator is injectable so the rest of the app — and
the tests — don't need librosa unless real analysis runs.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..config import Settings
from ..download.base import Track
from .bpm import bucket, estimate_raw_bpm, fold_octave

Estimator = Callable[[Path], float]


def analyze_bpm(track: Track, settings: Settings, *, estimator: Estimator = estimate_raw_bpm) -> Track:
    if track.file_path is None:
        return track.update(status="failed")
    raw = estimator(track.file_path)
    bpm = fold_octave(raw, settings.octave_low, settings.octave_high)
    return track.update(
        bpm=bpm,
        bpm_bucket=bucket(bpm, settings.bucket_width),
        status="analyzing",
    )
