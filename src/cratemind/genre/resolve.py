"""Resolve a track's genre through a fallback chain.

Order, most specific first: embedded tag → audio classifier → artist-genre lookup
→ coarse Deezer lookup → artist name (group by artist instead of `unsorted`).
Candidates are canonicalized; the artist name is returned verbatim to keep its
casing ("T78", not "t78"). The lookups are injectable so tests pass fakes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from ..download.base import Track
from .canonical import canonicalize

ArtistGenreLookup = Callable[[str], str | None]
CoarseGenreLookup = Callable[[str, str], str | None]
# The audio lookup may return a bare label or a (label, confidence) pair — the
# real model reports its winning-class probability; simple fakes return a str.
AudioGenreLookup = Callable[[Path], "str | tuple[str, float] | None"]


def resolve_genre(
    track: Track,
    *,
    audio_genre_lookup: AudioGenreLookup | None = None,
    artist_genre_lookup: ArtistGenreLookup | None = None,
    coarse_genre_lookup: CoarseGenreLookup | None = None,
    aliases: Mapping[str, str] | None = None,
) -> tuple[str | None, float | None]:
    """Resolve (genre, confidence). Confidence is set only when the audio model
    chose the genre — no other source has a comparable score."""
    tagged = canonicalize(track.genre, aliases)
    if tagged:
        return tagged, None
    if audio_genre_lookup is not None and track.file_path is not None:
        guess = audio_genre_lookup(track.file_path)
        label, score = guess if isinstance(guess, tuple) else (guess, None)
        from_audio = canonicalize(label, aliases)
        if from_audio:
            return from_audio, score
    if artist_genre_lookup is not None:
        from_artist = canonicalize(artist_genre_lookup(track.artist), aliases)
        if from_artist:
            return from_artist, None
    if coarse_genre_lookup is not None:
        coarse = canonicalize(coarse_genre_lookup(track.artist, track.title), aliases)
        if coarse:
            return coarse, None
    # Last resort: group by artist. Preserve the original casing for the folder;
    # fall through to None (→ `unsorted`) only when there's no artist at all.
    artist = (track.artist or "").strip()
    return artist or None, None
