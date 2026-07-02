from pathlib import Path

from cratemind.config import Settings
from cratemind.download.base import Track
from cratemind.organize.sorter import sort_track
from cratemind.pipeline import apply_previewed, process_track


def _make_file(tmp_path: Path, name: str = "song.flac") -> Path:
    path = tmp_path / name
    path.write_bytes(b"\x00")
    return path


def _analyzed_flac(tmp_path: Path) -> Track:
    return Track(
        spotify_id="1", title="Nightcall", artist="Kavinsky", genre="synthwave",
        bpm=118, key="8A", file_path=_make_file(tmp_path), status="downloading",
    )


def test_process_track_embeds_tags_into_sorted_file(tmp_path):
    calls: list[dict] = []
    process_track(
        _analyzed_flac(tmp_path),
        Settings(output_dir=tmp_path / "out"),
        estimator=lambda _p: 118,
        key_estimator=lambda _p: "8A",
        audio_genre_lookup=None,
        coarse_genre_lookup=None,
        tag_writer=lambda path, **kw: calls.append({"path": path, **kw}),
    )
    assert len(calls) == 1
    assert calls[0]["key"] == "8A" and calls[0]["bpm"] == 118
    assert calls[0]["notation"] == "camelot"
    assert calls[0]["path"].exists()  # writes to the post-sort path


def test_process_track_skips_tags_when_opted_out(tmp_path):
    calls: list[Path] = []
    process_track(
        _analyzed_flac(tmp_path),
        Settings(output_dir=tmp_path / "out", write_tags=False),
        estimator=lambda _p: 118,
        key_estimator=lambda _p: "8A",
        audio_genre_lookup=None,
        coarse_genre_lookup=None,
        tag_writer=lambda path, **kw: calls.append(path),
    )
    assert calls == []  # opt-out -> no tag writing


def test_sort_track_applies_custom_alias_from_settings(tmp_path):
    # A user-defined alias in settings folds the tagged genre into the chosen name.
    out = tmp_path / "out"
    src = _make_file(tmp_path)
    track = Track(
        spotify_id="1", title="x", artist="A", genre="techno",
        bpm=130, bpm_bucket="128-135", file_path=src,
    )
    result = sort_track(track, Settings(output_dir=out, aliases={"techno": "warehouse"}))
    assert result.genre == "warehouse"
    assert result.file_path == out / "warehouse" / "128-135" / "song.flac"


def test_sort_track_moves_into_genre_bucket(tmp_path):
    out = tmp_path / "out"
    src = _make_file(tmp_path)
    track = Track(
        spotify_id="1",
        title="Nightcall",
        artist="Kavinsky",
        genre="synthwave",
        bpm=118,
        bpm_bucket="112-119",
        file_path=src,
    )
    result = sort_track(track, Settings(output_dir=out))
    assert result.status == "sorted"
    assert result.file_path == out / "synthwave" / "112-119" / "song.flac"
    assert result.file_path.exists()
    assert not src.exists()  # moved out of the root, not copied — one file per track


def test_sort_track_groups_by_artist_without_genre(tmp_path):
    # No genre resolves (no lookups injected) → group by artist, not `unsorted`.
    out = tmp_path / "out"
    src = _make_file(tmp_path)
    track = Track(
        spotify_id="1",
        title="x",
        artist="Timmo",
        genre=None,
        bpm=96,
        bpm_bucket="96-103",
        file_path=src,
    )
    result = sort_track(track, Settings(output_dir=out))
    assert result.file_path == out / "Timmo" / "96-103" / "song.flac"
    assert result.genre == "Timmo"


def test_name_collision_gets_suffix(tmp_path):
    out = tmp_path / "out"
    settings = Settings(output_dir=out)
    common = {"genre": "house", "bpm": 124, "bpm_bucket": "120-127"}
    first = Track(spotify_id="1", title="x", artist="y", file_path=_make_file(tmp_path, "a.flac"), **common)
    sort_track(first, settings)
    second = Track(spotify_id="2", title="x", artist="y", file_path=_make_file(tmp_path, "a.flac"), **common)
    result = sort_track(second, settings)
    assert result.file_path.name == "a (1).flac"


def test_dry_run_touches_nothing_and_proposes_the_real_destination(tmp_path):
    out = tmp_path / "out"
    src = _make_file(tmp_path)
    track = Track(
        spotify_id="1", title="x", artist="A", genre="synthwave",
        bpm=118, bpm_bucket="112-119", file_path=src,
    )
    previewed = sort_track(track, Settings(output_dir=out, dry_run=True))
    assert previewed.status == "previewed"
    assert previewed.proposed_path == out / "synthwave" / "112-119" / "song.flac"
    assert previewed.file_path == src and src.exists()  # nothing moved
    assert not out.exists()  # not even a mkdir
    # The same track sorted for real lands exactly where the preview said.
    sorted_track = sort_track(track, Settings(output_dir=out))
    assert sorted_track.file_path == previewed.proposed_path


def test_dry_run_preview_shows_collision_suffix(tmp_path):
    out = tmp_path / "out"
    settings = Settings(output_dir=out)
    common = {"genre": "house", "bpm": 124, "bpm_bucket": "120-127"}
    first = Track(spotify_id="1", title="x", artist="y", file_path=_make_file(tmp_path, "a.flac"), **common)
    sort_track(first, settings)  # a.flac now on disk at the destination
    second = Track(spotify_id="2", title="x", artist="y", file_path=_make_file(tmp_path, "a.flac"), **common)
    previewed = sort_track(second, settings.with_(dry_run=True))
    assert previewed.proposed_path.name == "a (1).flac"


def test_already_at_destination_is_a_noop_not_a_rename(tmp_path):
    out = tmp_path / "out"
    dest_dir = out / "house" / "120-127"
    dest_dir.mkdir(parents=True)
    src = _make_file(dest_dir, "a.flac")  # file already sits at its destination
    track = Track(
        spotify_id="1", title="x", artist="y", genre="house",
        bpm=124, bpm_bucket="120-127", file_path=src,
    )
    result = sort_track(track, Settings(output_dir=out))
    assert result.status == "sorted"
    assert result.file_path == src and src.exists()
    assert not (dest_dir / "a (1).flac").exists()  # no self-collision rename
    previewed = sort_track(track, Settings(output_dir=out, dry_run=True))
    assert previewed.status == "previewed"
    assert previewed.proposed_path == src


def test_dry_run_respects_the_escape_guard(tmp_path):
    out = tmp_path / "out"
    src = _make_file(tmp_path)
    track = Track(
        spotify_id="1", title="x", artist="y", genre="techno",
        bpm=130, bpm_bucket="128-135", file_path=src,
    )
    settings = Settings(output_dir=out, folder_template="../{genre}/", dry_run=True)
    previewed = sort_track(track, settings)
    assert previewed.proposed_path.is_relative_to(out.resolve())  # never escapes
    assert "unsorted" in previewed.proposed_path.parts


def test_apply_previewed_moves_and_tags_at_the_proposed_path(tmp_path):
    out = tmp_path / "out"
    src = _make_file(tmp_path)
    track = Track(
        spotify_id="1", title="x", artist="A", genre="synthwave", key="8A",
        bpm=118, bpm_bucket="112-119", file_path=src,
    )
    previewed = sort_track(track, Settings(output_dir=out, dry_run=True))
    calls: list[Path] = []
    done = apply_previewed(
        previewed, Settings(output_dir=out), tag_writer=lambda p, **kw: calls.append(p)
    )
    assert done.status == "sorted"
    assert done.file_path == out / "synthwave" / "112-119" / "song.flac"
    assert done.file_path.exists() and not src.exists()
    assert done.proposed_path is None
    assert calls == [done.file_path]  # tags written on apply, at the final path


def test_apply_previewed_ignores_settings_changes_for_the_destination(tmp_path):
    # The preview is the contract: a changed output_dir between preview and
    # apply must not redirect the move.
    old_out, new_out = tmp_path / "old", tmp_path / "new"
    src = _make_file(tmp_path)
    track = Track(
        spotify_id="1", title="x", artist="A", genre="house",
        bpm=124, bpm_bucket="120-127", file_path=src,
    )
    previewed = sort_track(track, Settings(output_dir=old_out, dry_run=True))
    done = apply_previewed(
        previewed, Settings(output_dir=new_out), tag_writer=lambda p, **kw: None
    )
    assert done.file_path.is_relative_to(old_out)
    assert not new_out.exists()


def test_apply_previewed_suffixes_a_collision_that_appeared_after_preview(tmp_path):
    out = tmp_path / "out"
    src = _make_file(tmp_path, "a.flac")
    track = Track(
        spotify_id="1", title="x", artist="y", genre="house",
        bpm=124, bpm_bucket="120-127", file_path=src,
    )
    previewed = sort_track(track, Settings(output_dir=out, dry_run=True))
    # Someone else lands a file at the previewed name before Apply runs.
    previewed.proposed_path.parent.mkdir(parents=True)
    previewed.proposed_path.write_bytes(b"\x00")
    done = apply_previewed(previewed, Settings(output_dir=out), tag_writer=lambda p, **kw: None)
    assert done.status == "sorted"
    assert done.file_path.name == "a (1).flac"


def test_apply_previewed_missing_source_degrades_to_failed(tmp_path):
    out = tmp_path / "out"
    src = _make_file(tmp_path)
    track = Track(
        spotify_id="1", title="x", artist="A", genre="house",
        bpm=124, bpm_bucket="120-127", file_path=src,
    )
    previewed = sort_track(track, Settings(output_dir=out, dry_run=True))
    src.unlink()  # user deleted it between preview and apply
    done = apply_previewed(previewed, Settings(output_dir=out), tag_writer=lambda p, **kw: None)
    assert done.status == "failed"


def test_apply_previewed_in_place_is_a_noop_move(tmp_path):
    out = tmp_path / "out"
    dest_dir = out / "house" / "120-127"
    dest_dir.mkdir(parents=True)
    src = _make_file(dest_dir, "a.flac")
    track = Track(
        spotify_id="1", title="x", artist="y", genre="house",
        bpm=124, bpm_bucket="120-127", file_path=src,
    )
    previewed = sort_track(track, Settings(output_dir=out, dry_run=True))
    assert previewed.proposed_path == src
    done = apply_previewed(previewed, Settings(output_dir=out), tag_writer=lambda p, **kw: None)
    assert done.status == "sorted"
    assert done.file_path == src and src.exists()
    assert not (dest_dir / "a (1).flac").exists()


def test_process_track_skips_deezer_when_online_genre_off(tmp_path):
    src = _make_file(tmp_path, "t.flac")
    called: list[tuple[str, str]] = []
    track = Track(spotify_id="1", title="x", artist="Timmo", genre=None, file_path=src)
    result = process_track(
        track,
        Settings(output_dir=tmp_path / "out", online_genre=False),
        estimator=lambda _p: 130.0,
        key_estimator=lambda _p: "8A",
        audio_genre_lookup=lambda _p: None,
        coarse_genre_lookup=lambda a, t: called.append((a, t)) or "electronic",
    )
    assert called == []  # Deezer not consulted when the toggle is off
    assert result.genre == "Timmo"  # fell through to artist grouping


def test_process_track_uses_deezer_when_online_genre_on(tmp_path):
    src = _make_file(tmp_path, "t.flac")
    track = Track(spotify_id="1", title="x", artist="Timmo", genre=None, file_path=src)
    result = process_track(
        track,
        Settings(output_dir=tmp_path / "out", online_genre=True),
        estimator=lambda _p: 130.0,
        key_estimator=lambda _p: "8A",
        audio_genre_lookup=lambda _p: None,
        coarse_genre_lookup=lambda _a, _t: "electronic",
    )
    assert result.genre == "electronic"


def test_process_track_end_to_end(tmp_path):
    out = tmp_path / "out"
    src = _make_file(tmp_path, "track.flac")
    track = Track(spotify_id="1", title="Resonance", artist="HOME", genre="chillwave", file_path=src)
    result = process_track(
        track,
        Settings(output_dir=out),
        estimator=lambda _p: 110.0,
        key_estimator=lambda _p: "8A",
    )
    assert result.status == "sorted"
    assert result.bpm == 110
    assert result.key == "8A"
    assert result.file_path == out / "chillwave" / "104-111" / "track.flac"
    assert result.file_path.exists()
