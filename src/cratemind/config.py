"""User-facing settings with sane defaults. Immutable — updates return a copy."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

DEFAULT_TEMPLATE = "{genre}/{bpm_bucket}/"
AUDIO_FORMATS = ("flac", "mp3", "m4a")


def _default_output_dir() -> Path:
    return Path.home() / "Music" / "cratemind"


@dataclass(frozen=True)
class Settings:
    output_dir: Path = field(default_factory=_default_output_dir)
    audio_format: str = "flac"  # one of AUDIO_FORMATS
    folder_template: str = DEFAULT_TEMPLATE
    octave_low: int = 70
    octave_high: int = 180
    bucket_width: int = 8
    # Off by default: the genre fallback that queries Deezer by track name. The
    # local audio model covers most tracks; this trades some privacy for the tail.
    online_genre: bool = False

    def __post_init__(self) -> None:
        if self.audio_format not in AUDIO_FORMATS:
            raise ValueError(f"unsupported format: {self.audio_format!r}")
        if self.octave_high < self.octave_low * 2:
            raise ValueError("octave window must span at least one octave (high >= 2*low)")
        if self.bucket_width <= 0:
            raise ValueError("bucket_width must be positive")

    def with_(self, **changes: object) -> "Settings":
        return replace(self, **changes)
