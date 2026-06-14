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


def place_from_manifest(
    track: Track,
    settings: Settings,
    *,
    bpm: int | None,
    bpm_bucket: str | None,
    genre: str | None,
) -> Track:
    """Sort a downloaded track using a shared manifest's analysis — no librosa.

    Used on import: the BPM and genre come from the crate.json someone shared, so
    we just file the freshly downloaded file into the right folder.
    """
    enriched = track.update(bpm=bpm, bpm_bucket=bpm_bucket, genre=genre, status="analyzing")
    return sort_track(enriched, settings)
