"""Behaviour of embedding key/BPM/genre into a downloaded file's tags.

The key is written as the Camelot code by default (what most DJ software reads),
or musical notation for tools like Mixxx. MP3 is round-tripped through real
mutagen ID3 frames; the FLAC and MP4 field mappings are checked against dict-like
tag containers (their real tag objects are dict-like), avoiding synthesized audio.
"""

from __future__ import annotations

from mutagen.id3 import ID3

from cratemind.download import write_tags as wt


def test_key_value_camelot_passthrough_and_musical_conversion():
    assert wt._key_value("8A", "camelot") == "8A"
    assert wt._key_value("8A", "musical") == "Am"
    assert wt._key_value("", "camelot") == ""  # no key -> empty, nothing to write


def test_write_tags_mp3_roundtrip_camelot(tmp_path):
    path = tmp_path / "track.mp3"
    path.write_bytes(b"")  # ID3 writes its own chunk; no audio frames needed
    wt.write_tags(path, key="8A", bpm=128, genre="techno")
    tags = ID3(path)
    assert tags["TKEY"].text == ["8A"]
    assert tags["TBPM"].text == ["128"]
    assert tags["TCON"].text == ["techno"]


def test_write_tags_mp3_uses_musical_notation_when_requested(tmp_path):
    path = tmp_path / "track.mp3"
    path.write_bytes(b"")
    wt.write_tags(path, key="8A", bpm=120, genre="house", notation="musical")
    assert ID3(path)["TKEY"].text == ["Am"]


def test_apply_vorbis_sets_flac_fields():
    tags: dict[str, object] = {}
    wt._apply_vorbis(tags, "8A", 128, "techno")
    assert tags == {"INITIALKEY": "8A", "BPM": "128", "GENRE": "techno"}


def test_apply_vorbis_skips_empty_fields():
    tags: dict[str, object] = {}
    wt._apply_vorbis(tags, "", None, None)
    assert tags == {}  # nothing written when there's nothing to write


def test_apply_mp4_sets_atoms_with_correct_types():
    tags: dict[str, object] = {}
    wt._apply_mp4(tags, "8A", 128, "techno")
    assert tags["tmpo"] == [128]  # integer atom
    assert tags["©gen"] == ["techno"]
    assert bytes(tags["----:com.apple.iTunes:initialkey"][0]) == b"8A"


def test_write_tags_is_non_fatal_on_non_audio_file(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("not audio")
    wt.write_tags(path, key="8A", bpm=128, genre="techno")  # must not raise
