"""Entry point for `uv run cratemind` — launches the local web app."""

from __future__ import annotations


def main() -> None:
    import uvicorn

    uvicorn.run("cratemind.web.app:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
