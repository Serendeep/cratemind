"""SQLite store — the runtime source of truth.

Holds every track's state per run so reruns can skip what's already sorted, plus
settings and the genre alias map. Keyed on (run_url, spotify_id) so the same
playlist resumes cleanly.
"""

from __future__ import annotations

import sqlite3
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
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS aliases (name TEXT PRIMARY KEY, canonical TEXT);
"""

_DONE = "sorted"


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

    def aliases(self) -> dict[str, str]:
        rows = self.conn.execute("SELECT name, canonical FROM aliases").fetchall()
        return {r["name"]: r["canonical"] for r in rows}
