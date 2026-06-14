"""Resolve a track's genre through a fallback chain, ending in `unsorted`.

Order: the tag the downloader embedded (MusicBrainz via SpotiFLAC, Spotify via
spotdl) → an optional artist-genre lookup (e.g. Spotify's artist endpoint, which
is not deprecated) → None, which the folder layer renders as `unsorted`. Every
candidate is canonicalized so cross-source spellings collapse to one folder.
"""

from __future__ import annotations

from collections.abc import Callable

from ..download.base import Track
from .canonical import canonicalize

ArtistGenreLookup = Callable[[str], str | None]


def resolve_genre(
    track: Track,
    *,
    artist_genre_lookup: ArtistGenreLookup | None = None,
    aliases: dict[str, str] | None = None,
) -> str | None:
    tagged = canonicalize(track.genre, aliases)
    if tagged:
        return tagged
    if artist_genre_lookup is not None:
        from_artist = canonicalize(artist_genre_lookup(track.artist), aliases)
        if from_artist:
            return from_artist
    return None
