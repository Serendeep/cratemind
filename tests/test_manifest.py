import pytest
from pydantic import ValidationError

from cratemind.manifest import MANIFEST_VERSION, CrateManifest, TrackEntry


def test_roundtrip_preserves_data():
    crate = CrateManifest(
        playlist_url="https://open.spotify.com/playlist/abc",
        playlist_name="Late Night Drive",
        tracks=[
            TrackEntry(
                spotify_id="1",
                title="Nightcall",
                artist="Kavinsky",
                genre="synthwave",
                bpm=118,
                bpm_bucket="112-119",
            )
        ],
    )
    restored = CrateManifest.from_json(crate.to_json())
    assert restored == crate
    assert restored.version == MANIFEST_VERSION


def test_invalid_json_raises():
    with pytest.raises(ValidationError):
        CrateManifest.from_json("{not valid json}")


def test_playlist_url_is_required():
    with pytest.raises(ValidationError):
        CrateManifest(tracks=[])  # type: ignore[call-arg]
