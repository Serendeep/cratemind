"""In-memory job registry for crate runs.

A run is slow (downloads + analysis), so it executes off the request thread and
the UI polls the job for the current track list. `spawn` is injectable so tests
can run a job inline instead of on a background thread.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from ..config import Settings
from ..download.base import Track
from ..runner import run_crate
from ..store.db import CrateStore

Spawn = Callable[[Callable[[], None]], None]
Runner = Callable[..., "tuple[str, list[Track]]"]


def _thread_spawn(work: Callable[[], None]) -> None:
    threading.Thread(target=work, daemon=True).start()


@dataclass
class Job:
    id: str
    playlist_url: str
    status: str = "running"  # running | done | error
    error: str | None = None
    backend: str | None = None
    tracks: list[Track] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


class JobManager:
    def __init__(
        self,
        *,
        store_factory: Callable[[], CrateStore] = CrateStore,
        spawn: Spawn = _thread_spawn,
    ) -> None:
        self._jobs: dict[str, Job] = {}
        self._store_factory = store_factory
        self._spawn = spawn

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def start(
        self,
        playlist_url: str,
        settings: Settings,
        *,
        runner: Runner = run_crate,
        runner_kwargs: dict[str, object] | None = None,
    ) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], playlist_url=playlist_url)
        self._jobs[job.id] = job

        def on_update(track: Track) -> None:
            with job.lock:
                kept = [t for t in job.tracks if t.spotify_id != track.spotify_id]
                job.tracks = [*kept, track]

        def work() -> None:
            # The store owns a SQLite connection bound to the thread that opens
            # it, so create it here on the worker thread, not the caller's.
            store = self._store_factory()
            try:
                backend, _ = runner(
                    playlist_url, settings, store, on_update=on_update, **(runner_kwargs or {})
                )
                with job.lock:
                    job.backend = backend
                    job.status = "done"
            except Exception as error:  # surface in the UI, don't crash the server
                with job.lock:
                    job.status = "error"
                    job.error = str(error)
            finally:
                store.close()

        self._spawn(work)
        return job
