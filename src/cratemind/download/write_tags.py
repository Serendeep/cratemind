"""Embed analysis results (key, BPM, genre) into a downloaded file's tags.

cratemind sorts tracks into folders and keeps its analysis in its own store, but
DJ software reads metadata from the files themselves. This writes the key, BPM,
and genre into the standard tag fields so Rekordbox, Mixxx, Serato, etc. show
them on import.

The key is written as the Camelot code by default (e.g. "8A") — what most DJ
software reads. For tools that expect musical notation in the standard key frame
(notably Mixxx), pass ``notation="musical"`` to write "Am" instead.

Tagging is best-effort: a failure here never fails the sort — a sorted file
without embedded tags is still a sorted file. External dependency (mutagen) is
imported lazily so the rest of the app doesn't pay for it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..analysis.key import camelot_to_musical


def _key_value(camelot: str, notation: str) -> str:
    """Resolve the string to write into the key field for the chosen notation."""
    if not camelot:
        return ""
    return camelot if notation == "camelot" else camelot_to_musical(camelot)


def _apply_vorbis(tags: Any, key_value: str, bpm: int | None, genre: str | None) -> None:
    """FLAC / Vorbis comments — case-insensitive string fields on a dict-like tag."""
    if key_value:
        tags["INITIALKEY"] = key_value
    if bpm:
        tags["BPM"] = str(bpm)
    if genre:
        tags["GENRE"] = genre


def _apply_id3(tags: Any, key_value: str, bpm: int | None, genre: str | None) -> None:
    """MP3 — ID3v2 text frames."""
    from mutagen.id3 import TBPM, TCON, TKEY

    if key_value:
        tags.setall("TKEY", [TKEY(encoding=3, text=key_value)])
    if bpm:
        tags.setall("TBPM", [TBPM(encoding=3, text=str(bpm))])
    if genre:
        tags.setall("TCON", [TCON(encoding=3, text=genre)])


def _apply_mp4(tags: Any, key_value: str, bpm: int | None, genre: str | None) -> None:
    """M4A — MP4 atoms; key is a freeform atom, BPM an integer atom."""
    from mutagen.mp4 import MP4FreeForm

    if key_value:
        tags["----:com.apple.iTunes:initialkey"] = [MP4FreeForm(key_value.encode())]
    if bpm:
        tags["tmpo"] = [int(bpm)]
    if genre:
        tags["©gen"] = [genre]


def write_tags(
    path: Path,
    *,
    key: str = "",
    bpm: int | None = None,
    genre: str | None = None,
    notation: str = "camelot",
) -> None:
    """Embed key/BPM/genre into the file at ``path``. Best-effort; never raises."""
    try:
        import mutagen
        from mutagen.id3 import ID3, ID3NoHeaderError

        key_value = _key_value(key, notation)
        suffix = path.suffix.lower()

        if suffix == ".mp3":
            try:
                tags = ID3(path)
            except ID3NoHeaderError:
                tags = ID3()  # no existing tag yet — start a fresh one
            _apply_id3(tags, key_value, bpm, genre)
            tags.save(path)
            return

        audio = mutagen.File(path)
        if audio is None:
            return  # mutagen didn't recognise the container — nothing to do
        if audio.tags is None:
            audio.add_tags()
        if suffix == ".flac":
            _apply_vorbis(audio, key_value, bpm, genre)
        elif suffix in (".m4a", ".mp4"):
            _apply_mp4(audio, key_value, bpm, genre)
        else:
            return  # unsupported format — leave it untouched
        audio.save()
    except Exception:
        pass  # embedding tags is a nice-to-have; never fail the sort over it
