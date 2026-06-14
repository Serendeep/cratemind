from cratemind.download.base import Track
from cratemind.manifest import CrateManifest


def test_from_tracks_builds_entries_and_roundtrips():
    tracks = [
        Track(
            spotify_id="1",
            title="Nightcall",
            artist="Kavinsky",
            genre="synthwave",
            bpm=118,
            bpm_bucket="112-119",
            source="spotiflac",
            lossless=True,
        )
    ]
    crate = CrateManifest.from_tracks(
        "https://open.spotify.com/playlist/abc", tracks, playlist_name="Late Night Drive"
    )
    assert crate.playlist_name == "Late Night Drive"
    assert crate.tracks[0].spotify_id == "1"
    assert crate.tracks[0].bpm == 118
    assert CrateManifest.from_json(crate.to_json()) == crate
