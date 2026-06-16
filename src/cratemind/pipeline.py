"""Per-track pipeline: analyze BPM, resolve genre, file into the crate.

This is the seam the web layer drives, emitting each returned Track so the UI
can show the download → analyze → sort progression.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .analysis.analyzer import Estimator, analyze_bpm
from .analysis.bpm import estimate_raw_bpm
from .analysis.key import estimate_camelot
from .config import Settings
from .download.base import Track
from .download.write_tags import write_tags
from .genre.audio import lookup_audio_genre
from .genre.deezer import lookup_deezer_genre
from .genre.resolve import ArtistGenreLookup, AudioGenreLookup, CoarseGenreLookup
from .organize.sorter import sort_track

KeyEstimator = Callable[[Path], str]
TagWriter = Callable[..., None]


def _embed_tags(track: Track, settings: Settings, tag_writer: TagWriter) -> None:
    """Write the analysis into the sorted file's tags, when enabled."""
    if not settings.write_tags or track.status != "sorted" or track.file_path is None:
        return
    tag_writer(
        track.file_path,
        key=track.key or "",
        bpm=track.bpm,
        genre=track.genre,
        notation=settings.key_notation,
    )


def process_track(
    track: Track,
    settings: Settings,
    *,
    estimator: Estimator = estimate_raw_bpm,
    key_estimator: KeyEstimator = estimate_camelot,
    audio_genre_lookup: AudioGenreLookup | None = lookup_audio_genre,
    coarse_genre_lookup: CoarseGenreLookup | None = lookup_deezer_genre,
    artist_genre_lookup: ArtistGenreLookup | None = None,
    tag_writer: TagWriter = write_tags,
) -> Track:
    analyzed = analyze_bpm(track, settings, estimator=estimator)
    if analyzed.status == "failed":
        return analyzed
    if analyzed.file_path is not None:
        analyzed = analyzed.update(key=key_estimator(analyzed.file_path) or None)
    # The Deezer fallback is the only step that leaves the machine; honor the
    # per-run opt-in so it stays off unless the user asked for it.
    coarse = coarse_genre_lookup if settings.online_genre else None
    sorted_track = sort_track(
        analyzed,
        settings,
        audio_genre_lookup=audio_genre_lookup,
        coarse_genre_lookup=coarse,
        artist_genre_lookup=artist_genre_lookup,
    )
    _embed_tags(sorted_track, settings, tag_writer)
    return sorted_track


def place_from_manifest(
    track: Track,
    settings: Settings,
    *,
    bpm: int | None,
    bpm_bucket: str | None,
    key: str | None,
    genre: str | None,
    tag_writer: TagWriter = write_tags,
) -> Track:
    """Sort a downloaded track using a shared manifest's analysis — no librosa.

    Used on import: the BPM and genre come from the crate.json someone shared, so
    we just file the freshly downloaded file into the right folder.
    """
    enriched = track.update(
        bpm=bpm, bpm_bucket=bpm_bucket, key=key, genre=genre, status="analyzing"
    )
    sorted_track = sort_track(enriched, settings)
    _embed_tags(sorted_track, settings, tag_writer)
    return sorted_track
