import os
import tempfile

import pytest

# Keep tests away from the real user-data directory.
os.environ.setdefault("CRATEMIND_DATA_DIR", tempfile.mkdtemp(prefix="cratemind-test-"))


@pytest.fixture(autouse=True)
def _no_real_downloads(monkeypatch):
    """Never let a test shell out to spotdl/SpotiFLAC, even if they're installed.

    Tests that need specific download behavior override `_run` themselves.
    """
    from cratemind.download import backends

    def _stub(_command):
        raise backends.BackendUnavailable("download tools are stubbed in tests")

    monkeypatch.setattr(backends, "_run", _stub)
