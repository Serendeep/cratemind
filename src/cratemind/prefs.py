"""Remember the user's last-used settings so they don't re-type them.

Stored as a small JSON file in the OS user-data directory. Corrupt or stale
prefs fall back to sane defaults rather than failing. CRATEMIND_DATA_DIR can
override the location (used by tests); regular users never touch it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import platformdirs

from .config import DEFAULT_TEMPLATE, Settings


def _data_dir() -> Path:
    override = os.environ.get("CRATEMIND_DATA_DIR")
    base = Path(override) if override else Path(platformdirs.user_data_dir("cratemind"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def prefs_path() -> Path:
    return _data_dir() / "prefs.json"


def load_settings() -> Settings:
    path = prefs_path()
    if not path.exists():
        return Settings()
    try:
        data = json.loads(path.read_text())
        return Settings(
            output_dir=Path(data["output_dir"]).expanduser(),
            audio_format=data.get("audio_format", "flac"),
            folder_template=data.get("folder_template", DEFAULT_TEMPLATE),
            octave_low=int(data.get("octave_low", 70)),
            octave_high=int(data.get("octave_high", 180)),
            bucket_width=int(data.get("bucket_width", 8)),
        )
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return Settings()  # corrupt or stale prefs -> sane defaults


def save_settings(settings: Settings) -> None:
    _ = prefs_path().write_text(
        json.dumps(
            {
                "output_dir": str(settings.output_dir),
                "audio_format": settings.audio_format,
                "folder_template": settings.folder_template,
                "octave_low": settings.octave_low,
                "octave_high": settings.octave_high,
                "bucket_width": settings.bucket_width,
            },
            indent=2,
        )
    )
