"""Orchestrate one crate run: fetch the playlist, then analyze + sort each track,
recording state in the store and emitting per-track updates for the UI.

Resume is per-track: a track already marked `sorted` for this playlist skips
re-analysis. (Whole-playlist re-download is the downloader's concern; that
finer-grained skip is a future refinement.)
"""

from __future__ import annotations

from collections.abc import Callable

from .config import Settings
from .download.backends import BackendUnavailable, fetch_playlist
from .download.base import Track
from .manifest import TrackEntry
from .pipeline import place_from_manifest, process_track
from .store.db import CrateStore

Fetch = Callable[[str, Settings], "tuple[str, list[Track]]"]
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
    backend_name, downloaded = fetch(playlist_url, settings)
    # Tracks already sorted on a prior run keep their analysis (bpm/genre/key) in
    # the store; only freshly-downloaded files (sitting in the output root) need
    # processing. fetch returns an empty list on a rerun where nothing was new.
    stored = store.tracks(playlist_url)
    sorted_before = [t for t in stored if t.status == "sorted"]
    done_ids = {t.spotify_id for t in sorted_before}
    new_tracks = [t for t in downloaded if t.spotify_id not in done_ids]

    if not new_tracks and not sorted_before:
        # Nothing downloaded this run and nothing sorted on a prior run — the
        # downloader genuinely produced nothing to show.
        raise BackendUnavailable(f"{backend_name} downloaded no tracks")

    results: list[Track] = []
    # Show the existing crate first so a rerun isn't blank while new files process.
    for track in sorted_before:
        results.append(track)
        if on_update:
            on_update(track)

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
    return backend_name, results
