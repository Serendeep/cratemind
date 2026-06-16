"""Entry point for `uv run cratemind` — launches the local web app.

On startup it makes ffmpeg findable for spotdl (see `ffmpeg.ensure_ffmpeg_on_path`)
so users never edit PATH. Subcommands:
  download-model  fetch the MAEST audio-genre model (~330 MB) into the cache
  setup-ffmpeg    fetch spotdl's portable ffmpeg into the cache (no system install)
With no arguments it runs the server.
"""

from __future__ import annotations

import sys


def main() -> None:
    from . import ffmpeg

    # Put ffmpeg on PATH for the download subprocesses before doing anything else.
    _ = ffmpeg.ensure_ffmpeg_on_path()

    if len(sys.argv) > 1:
        if sys.argv[1] == "download-model":
            from .genre.audio import download_model

            print("Downloading the audio-genre model (~330 MB)…")
            print(f"Done: {download_model()}")
            return
        if sys.argv[1] == "setup-ffmpeg":
            print("Fetching the portable ffmpeg via spotdl…")
            try:
                print(f"Done: {ffmpeg.download_ffmpeg()}")
            except ffmpeg.FFmpegUnavailable as exc:
                sys.exit(str(exc))  # actionable one-liner, not a traceback
            return
        hint = "(try no arguments, download-model, or setup-ffmpeg)"
        sys.exit(f"unknown command: {sys.argv[1]!r} {hint}")

    import uvicorn

    uvicorn.run("cratemind.web.app:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
