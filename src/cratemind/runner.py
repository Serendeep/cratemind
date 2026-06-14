"""Orchestrate one crate run: fetch the playlist, then analyze + sort each track,
recording state in the store and emitting per-track updates for the UI.

Resume is per-track: a track already marked `sorted` for this playlist skips
re-analysis. (Whole-playlist re-download is the downloader's concern; that
finer-grained skip is a future refinement.)
"""

from __future__ import annotations

from collections.abc import Callable

from .config import Settings
from .download.backends import fetch_playlist
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
    backend_name, tracks = fetch(playlist_url, settings)
    # Already-sorted tracks keep their analysis (bpm/genre/key) from a prior run;
    # read it from the store rather than the bare file so the UI stays complete.
    stored = {t.spotify_id: t for t in store.tracks(playlist_url)}
    results: list[Track] = []
    for track in tracks:
        if store.is_done(playlist_url, track.spotify_id):
            already = stored.get(track.spotify_id) or track.update(status="sorted")
            results.append(already)
            if on_update:
                on_update(already)
            continue
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
