"""SQLite store — the runtime source of truth.

Holds every track's state per run so reruns can skip what's already sorted, plus
settings and the genre alias map. Keyed on (run_url, spotify_id) so the same
playlist resumes cleanly.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..download.base import Track

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    run_url     TEXT NOT NULL,
    spotify_id  TEXT NOT NULL,
    title       TEXT,
    artist      TEXT,
    genre       TEXT,
    bpm         INTEGER,
    bpm_bucket  TEXT,
    key         TEXT,
    source      TEXT,
    lossless    INTEGER NOT NULL DEFAULT 0,
    file_path   TEXT,
    status      TEXT NOT NULL DEFAULT 'queued',
    PRIMARY KEY (run_url, spotify_id)
);
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    run_url     TEXT NOT NULL UNIQUE,
    name        TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS aliases (name TEXT PRIMARY KEY, canonical TEXT);
"""

_DONE = "sorted"


def run_id_for(run_url: str) -> str:
    """Short stable id for a run, for clean URLs (the run_url is long and ugly)."""
    return hashlib.sha1(run_url.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class RunSummary:
    """One past run for the crates list: identity, a name, and track counts."""

    run_id: str
    run_url: str
    name: str
    total: int
    sorted: int
    failed: int
    updated_at: str


def _to_track(row: sqlite3.Row) -> Track:
    return Track(
        spotify_id=row["spotify_id"],
        title=row["title"],
        artist=row["artist"],
        genre=row["genre"],
        bpm=row["bpm"],
        bpm_bucket=row["bpm_bucket"],
        key=row["key"],
        source=row["source"],
        lossless=bool(row["lossless"]),
        file_path=Path(row["file_path"]) if row["file_path"] else None,
        status=row["status"],
    )


class CrateStore:
    def __init__(self, path: Path | str = ":memory:") -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        _ = self.conn.executescript(_SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def upsert_track(self, run_url: str, track: Track) -> None:
        _ = self.conn.execute(
            """
            INSERT INTO tracks
                (run_url, spotify_id, title, artist, genre, bpm, bpm_bucket,
                 key, source, lossless, file_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_url, spotify_id) DO UPDATE SET
                title=excluded.title, artist=excluded.artist, genre=excluded.genre,
                bpm=excluded.bpm, bpm_bucket=excluded.bpm_bucket, key=excluded.key,
                source=excluded.source, lossless=excluded.lossless,
                file_path=excluded.file_path, status=excluded.status
            """,
            (
                run_url,
                track.spotify_id,
                track.title,
                track.artist,
                track.genre,
                track.bpm,
                track.bpm_bucket,
                track.key,
                track.source,
                int(track.lossless),
                str(track.file_path) if track.file_path else None,
                track.status,
            ),
        )
        self.conn.commit()

    def status_of(self, run_url: str, spotify_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT status FROM tracks WHERE run_url=? AND spotify_id=?",
            (run_url, spotify_id),
        ).fetchone()
        return row["status"] if row else None

    def is_done(self, run_url: str, spotify_id: str) -> bool:
        return self.status_of(run_url, spotify_id) == _DONE

    def tracks(self, run_url: str) -> list[Track]:
        rows = self.conn.execute(
            "SELECT * FROM tracks WHERE run_url=? ORDER BY artist, title",
            (run_url,),
        ).fetchall()
        return [_to_track(r) for r in rows]

    # runs ----------------------------------------------------------------
    def upsert_run(self, run_url: str, name: str | None = None) -> None:
        """Record (or touch) a run. A given name overwrites; None keeps the old."""
        now = datetime.now(timezone.utc).isoformat()
        _ = self.conn.execute(
            """
            INSERT INTO runs (run_id, run_url, name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                updated_at=excluded.updated_at,
                name=COALESCE(excluded.name, runs.name)
            """,
            (run_id_for(run_url), run_url, name, now, now),
        )
        self.conn.commit()

    def run_name(self, run_url: str) -> str | None:
        """The playlist name recorded for a run, or None if unknown/unrecorded."""
        row = self.conn.execute(
            "SELECT name FROM runs WHERE run_id=?", (run_id_for(run_url),)
        ).fetchone()
        return row["name"] if row else None

    def runs(self) -> list[RunSummary]:
        """Every recorded run with its track counts, most recently updated first."""
        rows = self.conn.execute(
            """
            SELECT r.run_id, r.run_url, r.name, r.updated_at,
                   COUNT(t.spotify_id) AS total,
                   SUM(CASE WHEN t.status='sorted' THEN 1 ELSE 0 END) AS sorted,
                   SUM(CASE WHEN t.status='failed' THEN 1 ELSE 0 END) AS failed
            FROM runs r LEFT JOIN tracks t ON t.run_url = r.run_url
            GROUP BY r.run_id
            ORDER BY r.updated_at DESC
            """
        ).fetchall()
        return [
            RunSummary(
                run_id=r["run_id"],
                run_url=r["run_url"],
                name=r["name"] or r["run_url"],
                total=r["total"] or 0,
                sorted=r["sorted"] or 0,
                failed=r["failed"] or 0,
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def run_url_for_id(self, run_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT run_url FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        return row["run_url"] if row else None

    # settings ------------------------------------------------------------
    def set_setting(self, key: str, value: str) -> None:
        _ = self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def get_setting(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    # alias map -----------------------------------------------------------
    def set_alias(self, name: str, canonical: str) -> None:
        _ = self.conn.execute(
            "INSERT INTO aliases (name, canonical) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET canonical=excluded.canonical",
            (name, canonical),
        )
        self.conn.commit()

    def delete_alias(self, name: str) -> None:
        _ = self.conn.execute("DELETE FROM aliases WHERE name=?", (name,))
        self.conn.commit()

    def aliases(self) -> dict[str, str]:
        rows = self.conn.execute("SELECT name, canonical FROM aliases ORDER BY name").fetchall()
        return {r["name"]: r["canonical"] for r in rows}
