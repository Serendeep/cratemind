"""Orchestrate one crate run: fetch the playlist, then analyze + sort each track,
recording state in the store and emitting per-track updates for the UI.

Resume is per-track: a track already marked `sorted` for this playlist skips
re-analysis. (Whole-playlist re-download is the downloader's concern; that
finer-grained skip is a future refinement.)
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from .config import Settings
from .download.backends import (
    BackendUnavailable,
    cleanup_staging,
    fetch_playlist,
    normalize_title,
)
from .download.base import Track
from .manifest import TrackEntry
from .pipeline import apply_previewed, place_from_manifest, process_track
from .store.db import CrateStore

Fetch = Callable[
    [str, Settings],
    "tuple[str, list[Track]] | tuple[str, list[Track], str | None]",
]
Process = Callable[[Track, Settings], Track]
OnUpdate = Callable[[Track], None]


def run_crate(
    playlist_url: str,
    settings: Settings,
    store: CrateStore,
    *,
    fetch: Fetch = fetch_playlist,
    process: Process = process_track,
    on_update: OnUpdate | None = None,
    overrides: dict[str, TrackEntry] | None = None,
) -> tuple[str, list[Track]]:
    result = fetch(playlist_url, settings)
    # fetch_playlist returns (backend, tracks, playlist_name); test fakes return
    # the 2-tuple. fetched holds downloaded files plus failed stubs (playlist songs
    # spotdl couldn't get, file_path None, status "failed"). Tracks already sorted
    # on a prior run keep their analysis in the store; only new files are processed.
    if len(result) == 3:
        backend_name, fetched, playlist_name = result
    else:
        backend_name, fetched = result
        playlist_name = None
    # Apply the user's saved genre aliases for this run (carried on settings so
    # the pure sort/resolve layers don't need the store).
    settings = settings.with_(aliases=store.aliases())
    stored = store.tracks(playlist_url)
    sorted_before = [t for t in stored if t.status == "sorted"]
    # Previewed tracks resume differently: their analysis is done (skip librosa)
    # but their genre resolution and destination must be recomputed, so the
    # preview → add alias / tweak template → re-preview loop actually refreshes.
    previewed_before = [t for t in stored if t.status == "previewed"]
    done_ids = {t.spotify_id for t in sorted_before}
    skip_ids = done_ids | {t.spotify_id for t in previewed_before}

    failed_stubs = [t for t in fetched if t.status == "failed" and t.file_path is None]
    downloads = [t for t in fetched if not (t.status == "failed" and t.file_path is None)]
    new_tracks = [t for t in downloads if t.spotify_id not in skip_ids]

    # Only surface a failure for a song we don't already have (this run or a prior
    # sorted run), matched by title so artist-string differences don't false-flag.
    have_titles = {normalize_title(t.title) for t in sorted_before}
    have_titles |= {normalize_title(t.title) for t in downloads}
    failures = [
        t
        for t in failed_stubs
        if normalize_title(t.title) not in have_titles and t.spotify_id not in done_ids
    ]

    if not new_tracks and not sorted_before and not previewed_before and not failures:
        # Nothing downloaded this run and nothing from a prior run — the
        # downloader genuinely produced nothing to show.
        raise BackendUnavailable(f"{backend_name} downloaded no tracks")

    # Record the run so it shows up in the crates list and can be re-exported later.
    store.upsert_run(playlist_url, name=playlist_name)

    results: list[Track] = []
    # Show the existing crate first so a rerun isn't blank while new files process.
    for track in sorted_before:
        results.append(track)
        if on_update:
            on_update(track)

    # Re-sort previewed tracks from their stored analysis — the manifest path:
    # no librosa, aliases re-apply, proposed_path recomputes. With dry_run off
    # (preview box unticked on the re-run) this same path performs the moves.
    for track in previewed_before:
        refreshed = place_from_manifest(
            track,
            settings,
            bpm=track.bpm,
            bpm_bucket=track.bpm_bucket,
            key=track.key,
            genre=track.genre,
        )
        store.upsert_track(playlist_url, refreshed)
        if on_update:
            on_update(refreshed)
        results.append(refreshed)

    for track in new_tracks:
        downloading = track.update(status="downloading")
        store.upsert_track(playlist_url, downloading)
        if on_update:
            on_update(downloading)
        entry = overrides.get(track.spotify_id) if overrides else None
        if entry is not None:
            done = place_from_manifest(
                downloading,
                settings,
                bpm=entry.bpm,
                bpm_bucket=entry.bpm_bucket,
                key=entry.key,
                genre=entry.genre,
            )
        else:
            done = process(downloading, settings)
        store.upsert_track(playlist_url, done)
        if on_update:
            on_update(done)
        results.append(done)

    # Songs spotdl couldn't download — record and show them so they aren't silent.
    for track in failures:
        store.upsert_track(playlist_url, track)
        results.append(track)
        if on_update:
            on_update(track)
    # A fully sorted run leaves its staging dir empty — drop it. A previewed
    # run's files are still inside, so this refuses (by design) until Apply.
    cleanup_staging(playlist_url, settings)
    return backend_name, results


Apply = Callable[[Track, Settings], Track]

# Serializes check-move-record per track so two concurrent Apply jobs (double
# click, stale tab) can't interleave: without it, the loser's "source vanished
# → failed" upsert could land after the winner's "sorted" and corrupt the row.
_APPLY_LOCK = threading.Lock()


def apply_crate(
    run_url: str,
    settings: Settings,
    store: CrateStore,
    *,
    apply: Apply = apply_previewed,
    on_update: OnUpdate | None = None,
) -> tuple[str, list[Track]]:
    """Move every previewed track of a run to its proposed destination.

    Idempotent per track: each row's status is re-read from the store just
    before acting, and only "previewed" rows move — anything else is re-emitted
    untouched. Repeating apply (or racing it) is therefore always safe.
    """
    settings = settings.with_(aliases=store.aliases())
    store.upsert_run(run_url)
    results: list[Track] = []
    for track in store.tracks(run_url):
        with _APPLY_LOCK:
            if store.status_of(run_url, track.spotify_id) != "previewed":
                results.append(track)
                if on_update:
                    on_update(track)
                continue
            done = apply(track, settings)
            store.upsert_track(run_url, done)
        if on_update:
            on_update(done)
        results.append(done)
    # Applying moves the last files out of the run's staging dir — drop it.
    cleanup_staging(run_url, settings)
    return "apply", results
