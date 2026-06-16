"""Entry point for `uv run cratemind` — launches the local web app.

`cratemind download-model` fetches the MAEST audio-genre model (~330 MB) into the
user cache so genre classification works offline; with no args it runs the server.
"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) > 1:
        if sys.argv[1] == "download-model":
            from .genre.audio import download_model

            print("Downloading the audio-genre model (~330 MB)…")
            print(f"Done: {download_model()}")
            return
        sys.exit(f"unknown command: {sys.argv[1]!r} (try no arguments, or download-model)")

    import uvicorn

    uvicorn.run("cratemind.web.app:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
