"""Portable `crate.json` interchange format.

Carries the analysis (per-track id/title/artist/genre/bpm) — never audio.
Importing a manifest lets cratemind re-download the same tracks and folder
them identically, skipping re-analysis. Versioned + schema-validated.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field

from .download.base import Track

MANIFEST_VERSION = 1


class TrackEntry(BaseModel):
    spotify_id: str
    title: str
    artist: str
    genre: str | None = None
    bpm: int | None = None
    bpm_bucket: str | None = None
    key: str | None = None


class CrateManifest(BaseModel):
    version: int = MANIFEST_VERSION
    playlist_url: str
    playlist_name: str | None = None
    tracks: list[TrackEntry] = Field(default_factory=list)

    @classmethod
    def from_tracks(
        cls,
        playlist_url: str,
        tracks: Iterable[Track],
        *,
        playlist_name: str | None = None,
    ) -> "CrateManifest":
        return cls(
            playlist_url=playlist_url,
            playlist_name=playlist_name,
            tracks=[
                TrackEntry(
                    spotify_id=t.spotify_id,
                    title=t.title,
                    artist=t.artist,
                    genre=t.genre,
                    bpm=t.bpm,
                    bpm_bucket=t.bpm_bucket,
                    key=t.key,
                )
                for t in tracks
            ],
        )

    @classmethod
    def from_json(cls, data: str) -> "CrateManifest":
        return cls.model_validate_json(data)

    def to_json(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)
