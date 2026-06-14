"""Per-track pipeline: analyze BPM, resolve genre, file into the crate.

This is the seam the web layer drives, emitting each returned Track so the UI
can show the download → analyze → sort progression.
"""

from __future__ import annotations

from .analysis.analyzer import Estimator, analyze_bpm
from .analysis.bpm import estimate_raw_bpm
from .config import Settings
from .download.base import Track
from .genre.resolve import ArtistGenreLookup
from .organize.sorter import sort_track


def process_track(
    track: Track,
    settings: Settings,
    *,
    estimator: Estimator = estimate_raw_bpm,
    artist_genre_lookup: ArtistGenreLookup | None = None,
) -> Track:
    analyzed = analyze_bpm(track, settings, estimator=estimator)
    if analyzed.status == "failed":
        return analyzed
    return sort_track(analyzed, settings, artist_genre_lookup=artist_genre_lookup)
