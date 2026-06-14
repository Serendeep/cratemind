"""Presentation helpers — shape Tracks into what the templates render."""

from __future__ import annotations

from collections import Counter

from ..download.base import Track

_STATUS_RANK = {"downloading": 0, "analyzing": 1, "queued": 2, "failed": 3, "sorted": 4}


def ordered_tracks(tracks: list[Track]) -> list[Track]:
    return sorted(
        tracks,
        key=lambda t: (_STATUS_RANK.get(t.status, 9), t.artist or "", t.title or ""),
    )


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
        "genres": len({t.genre for t in tracks if t.genre}),
        "unsorted": sum(1 for t in tracks if t.status == "sorted" and not t.genre),
        "lossless_pct": round(100 * lossless / total) if total else 0,
        "bins": [(label, count, round(100 * count / bin_max)) for label, count in bin_rows],
    }
