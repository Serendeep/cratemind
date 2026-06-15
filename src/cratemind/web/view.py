"""Presentation helpers — shape Tracks into what the templates render."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..download.base import Track

_STATUS_RANK = {"downloading": 0, "analyzing": 1, "queued": 2, "failed": 3, "sorted": 4}

PAGE_SIZE = 15


def ordered_tracks(tracks: list[Track]) -> list[Track]:
    return sorted(
        tracks,
        key=lambda t: (_STATUS_RANK.get(t.status, 9), t.artist or "", t.title or ""),
    )


@dataclass(frozen=True)
class Page:
    """One slice of the ordered track list, plus where it sits in the whole."""

    tracks: list[Track]
    number: int
    total: int


def paginate(tracks: list[Track], page: int, size: int = PAGE_SIZE) -> Page:
    """Slice the ordered tracks (working first, sorted last) into a page.

    The requested ``page`` is clamped into ``1..total`` so a stale page number
    from the auto-poll (e.g. after tracks finish and the list shrinks) never
    renders an empty table.
    """
    ordered = ordered_tracks(tracks)
    total = max(1, (len(ordered) + size - 1) // size)
    number = min(max(1, page), total)
    start = (number - 1) * size
    return Page(tracks=ordered[start : start + size], number=number, total=total)


def summarize(tracks: list[Track]) -> dict[str, object]:
    total = len(tracks)
    status = Counter(t.status for t in tracks)
    lossless = sum(1 for t in tracks if t.lossless)
    bins = Counter(t.bpm_bucket for t in tracks if t.bpm_bucket)
    bin_rows = sorted(bins.items(), key=lambda kv: int(kv[0].split("-")[0]))
    bin_max = max(bins.values(), default=1)
    return {
        "total": total,
        "sorted": status.get("sorted", 0),
        "working": status.get("downloading", 0) + status.get("analyzing", 0),
        "queued": status.get("queued", 0),
        "failed": status.get("failed", 0),
        # A track grouped by artist (no real genre found) stores the artist name
        # as its genre; exclude those from the real-genre count and tally them
        # separately. Canonicalized genres are lowercase, so genre == artist only
        # happens for the artist fallback.
        "genres": len({t.genre for t in tracks if t.genre and t.genre != t.artist}),
        "by_artist": sum(1 for t in tracks if t.status == "sorted" and t.genre == t.artist),
        "lossless_pct": round(100 * lossless / total) if total else 0,
        # spotdl-only runs are never lossless, so the stat would read a flat 0%.
        # Show it only when a lossless backend (SpotiFLAC) actually delivered.
        "has_lossless": lossless > 0,
        "progress_pct": round(100 * status.get("sorted", 0) / total) if total else 0,
        "bins": [(label, count, round(100 * count / bin_max)) for label, count in bin_rows],
    }
