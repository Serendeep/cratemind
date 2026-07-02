"""Presentation helpers — shape Tracks into what the templates render."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..download.base import Track
from ..download.tags import read_art_cached

_STATUS_RANK = {
    "downloading": 0,
    "analyzing": 1,
    "queued": 2,
    "previewed": 3,
    "failed": 4,
    "sorted": 5,
}

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
        "previewed": status.get("previewed", 0),
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
        # A previewed track's analysis is done — it counts as progress. With
        # zero previewed tracks this reduces to the old sorted-only number.
        "progress_pct": (
            round(100 * (status.get("sorted", 0) + status.get("previewed", 0)) / total)
            if total
            else 0
        ),
        "bins": [(label, count, round(100 * count / bin_max)) for label, count in bin_rows],
    }


ArtReader = Callable[[Path], "tuple[bytes, str] | None"]


def art_ids(tracks: list[Track], *, reader: ArtReader = read_art_cached) -> set[str]:
    """The spotify_ids on this page whose files carry embedded art.

    Called only for non-running jobs (the done state doesn't poll), so the
    per-file reads happen once per page render, not every two seconds.
    """
    return {
        t.spotify_id
        for t in tracks
        if t.file_path is not None and reader(t.file_path) is not None
    }


def folder_tree(tracks: list[Track], root: Path | None = None) -> list[tuple[str, list[Track]]]:
    """Previewed tracks grouped by proposed folder, for the structure preview.

    Labels are relative to the run's output root when known, so the tree reads
    as `hard techno/140-147`, not an absolute path per row.
    """
    groups: dict[Path, list[Track]] = {}
    for track in tracks:
        if track.status == "previewed" and track.proposed_path is not None:
            groups.setdefault(track.proposed_path.parent, []).append(track)
    tree: list[tuple[str, list[Track]]] = []
    for folder in sorted(groups):
        label = str(folder)
        if root is not None:
            try:
                label = str(folder.relative_to(root))
            except ValueError:
                pass  # previewed against a different root — show it absolute
        tree.append((label, sorted(groups[folder], key=lambda t: (t.artist or "", t.title or ""))))
    return tree
