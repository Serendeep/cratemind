"""Settings invariants: validation and immutability.

Settings is a frozen dataclass; the `aliases` dict is frozen too so a stray
mutation can't leak across the copies that `with_` hands around.
"""

from __future__ import annotations

import pytest

from cratemind.config import Settings


def test_invalid_key_notation_rejected():
    with pytest.raises(ValueError):
        Settings(key_notation="bogus")


def test_aliases_are_read_only_after_construction():
    settings = Settings(aliases={"techno": "warehouse"})
    assert settings.aliases["techno"] == "warehouse"
    with pytest.raises(TypeError):  # frozen mapping rejects in-place mutation
        settings.aliases["techno"] = "house"
