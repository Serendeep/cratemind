from cratemind.genre.canonical import canonicalize


def test_expands_ampersand():
    assert canonicalize("Drum & Bass") == "drum and bass"


def test_applies_alias():
    assert canonicalize("dnb") == "drum and bass"


def test_lowercases_and_collapses_whitespace():
    assert canonicalize("  House   Music ") == "house music"


def test_blank_becomes_none():
    assert canonicalize("   ") is None


def test_none_passes_through():
    assert canonicalize(None) is None


def test_custom_alias_map_overrides_default():
    assert canonicalize("trap", {"trap": "hip hop"}) == "hip hop"
