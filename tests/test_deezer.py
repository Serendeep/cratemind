from cratemind.genre import deezer
from cratemind.genre.deezer import lookup_deezer_genre


def _fake_api(search_hit: dict | None, album: dict) -> object:
    def fetch_json(url: str) -> dict:
        if "/search" in url:
            return {"data": [search_hit]} if search_hit else {"data": []}
        return album

    return fetch_json


def test_deezer_folds_coarse_genre_to_clean_label():
    fetch = _fake_api(
        {"album": {"id": 99}},
        {"genres": {"data": [{"name": "Electro"}]}},  # Deezer's generic catch-all
    )
    assert lookup_deezer_genre("T78", "Bombacid", fetch_json=fetch) == "electronic"


def test_deezer_passes_through_specific_genre():
    fetch = _fake_api({"album": {"id": 1}}, {"genres": {"data": [{"name": "Trance"}]}})
    assert lookup_deezer_genre("X", "Y", fetch_json=fetch) == "trance"


def test_deezer_returns_none_on_no_match():
    assert lookup_deezer_genre("Nobody", "Nothing", fetch_json=_fake_api(None, {})) is None


def test_deezer_returns_none_when_album_has_no_genre():
    fetch = _fake_api({"album": {"id": 5}}, {"genres": {"data": []}})
    assert lookup_deezer_genre("X", "Y", fetch_json=fetch) is None


def test_deezer_encodes_query():
    seen: dict[str, str] = {}

    def fetch(url: str) -> dict:
        seen["url"] = url
        return {"data": []}

    lookup_deezer_genre("Lorenzo Raganzini", "Born Slippy", fetch_json=fetch)
    assert " " not in seen["url"]  # spaces must be percent-encoded
    assert "%22" in seen["url"]  # the literal quotes are encoded too


def test_deezer_swallows_fetch_errors():
    def boom(_url: str) -> dict:
        raise RuntimeError("network down")

    assert lookup_deezer_genre("X", "Y", fetch_json=boom) is None


def test_deezer_default_path_is_cached(monkeypatch):
    deezer._cached_lookup.cache_clear()
    calls = {"n": 0}

    def fake(url: str) -> dict:
        calls["n"] += 1
        if "/search" in url:
            return {"data": [{"album": {"id": 7}}]}
        return {"genres": {"data": [{"name": "Techno"}]}}

    monkeypatch.setattr(deezer, "_default_fetch_json", fake)
    assert deezer._cached_lookup("T78", "Bombacid") == "techno"
    assert deezer._cached_lookup("T78", "Bombacid") == "techno"
    assert calls["n"] == 2  # search + album once; the repeat is served from cache
    deezer._cached_lookup.cache_clear()
