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
from .organize.sorter import place_file, sort_track

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


def apply_previewed(
    track: Track,
    settings: Settings,
    *,
    tag_writer: TagWriter = write_tags,
) -> Track:
    """Perform the move a dry run proposed: place the file, then embed tags.

    The destination folder is re-derived from the stored `proposed_path` —
    never from current settings — so a prefs change between preview and apply
    can affect tag style but never where the file lands. `place_file` re-runs
    the unique-name check, so a collision that appeared since the preview still
    gets a suffix. A vanished source degrades to "failed"; the caller decides
    whether that's terminal (idempotency lives in the apply runner, which skips
    anything no longer "previewed").
    """
    if track.proposed_path is None or track.file_path is None:
        return track.update(status="failed")
    if track.file_path == track.proposed_path:
        # Previewed in place — nothing to move.
        done = track.update(status="sorted", proposed_path=None)
        _embed_tags(done, settings, tag_writer)
        return done
    if not track.file_path.exists():
        return track.update(status="failed")
    dest = place_file(track.file_path, track.proposed_path.parent)
    done = track.update(file_path=dest, proposed_path=None, status="sorted")
    _embed_tags(done, settings, tag_writer)
    return done


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
