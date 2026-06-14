"""FastAPI application. The HTMX UI is wired in the UI phase; this is the shell."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="cratemind")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
