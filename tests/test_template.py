from pathlib import Path

from cratemind.organize.template import UNSORTED, render_path, sanitize


def test_renders_genre_and_bucket():
    p = render_path(
        "{genre}/{bpm_bucket}/",
        genre="synthwave",
        bpm=118,
        bpm_bucket="112-119",
        artist="Kavinsky",
        year=2013,
    )
    assert p == Path("synthwave/112-119")


def test_missing_genre_falls_back_to_unsorted():
    p = render_path(
        "{genre}/{bpm_bucket}/",
        genre=None,
        bpm=96,
        bpm_bucket="96-103",
        artist="x",
        year=None,
    )
    assert p == Path(f"{UNSORTED}/96-103")


def test_sanitize_replaces_path_separators():
    assert sanitize("AC/DC") == "AC_DC"


def test_genre_with_slash_cannot_inject_path_levels():
    p = render_path(
        "{genre}/",
        genre="folk/rock",
        bpm=None,
        bpm_bucket=None,
        artist=None,
        year=None,
    )
    assert p == Path("folk_rock")
