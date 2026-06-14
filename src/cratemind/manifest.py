"""Portable `crate.json` interchange format.

Carries the analysis (per-track id/title/artist/genre/bpm) — never audio.
Importing a manifest lets cratemind re-download the same tracks and folder
them identically, skipping re-analysis. Versioned + schema-validated.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

MANIFEST_VERSION = 1


class TrackEntry(BaseModel):
    spotify_id: str
    title: str
    artist: str
    genre: str | None = None
    bpm: int | None = None
    bpm_bucket: str | None = None


class CrateManifest(BaseModel):
    version: int = MANIFEST_VERSION
    playlist_url: str
    playlist_name: str | None = None
    tracks: list[TrackEntry] = Field(default_factory=list)

    @classmethod
    def from_json(cls, data: str) -> "CrateManifest":
        return cls.model_validate_json(data)

    def to_json(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)
