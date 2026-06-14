import os
import tempfile

# Keep tests away from the real user-data directory.
os.environ.setdefault("CRATEMIND_DATA_DIR", tempfile.mkdtemp(prefix="cratemind-test-"))
