"""FastAPI application — serves the HTMX UI and drives crate runs."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .. import __version__
from ..config import DEFAULT_TEMPLATE, Settings
from ..manifest import CrateManifest
from .jobs import JobManager
from .view import ordered_tracks, summarize

_BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))

# Favicon: the same mark shown next to the wordmark — rounded square, ring, dot.
_FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect x="2" y="2" width="28" height="28" rx="6" fill="#0c0d0f" stroke="#989aa1" stroke-width="2"/>'
    '<circle cx="16" cy="16" r="7.5" fill="none" stroke="#989aa1" stroke-width="2"/>'
    '<circle cx="16" cy="16" r="2.4" fill="#7fb98a"/>'
    "</svg>"
)

app = FastAPI(title="cratemind")
jobs = JobManager()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/favicon.svg")
def favicon() -> Response:
    return Response(_FAVICON, media_type="image/svg+xml")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"version": __version__, "defaults": Settings()},
    )


def _results(request: Request, job) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_results.html",
        {
            "job": job,
            "tracks": ordered_tracks(job.tracks),
            "summary": summarize(job.tracks),
        },
    )


@app.post("/runs", response_class=HTMLResponse)
def start_run(
    request: Request,
    playlist_url: str = Form(...),
    output_dir: str = Form(...),
    audio_format: str = Form("flac"),
    folder_template: str = Form(DEFAULT_TEMPLATE),
    octave_low: int = Form(70),
    octave_high: int = Form(180),
    bucket_width: int = Form(8),
) -> HTMLResponse:
    settings = Settings(
        output_dir=Path(output_dir).expanduser(),
        audio_format=audio_format,
        folder_template=folder_template,
        octave_low=octave_low,
        octave_high=octave_high,
        bucket_width=bucket_width,
    )
    job = jobs.start(playlist_url, settings)
    return _results(request, job)


@app.post("/import", response_class=HTMLResponse)
async def import_crate(
    request: Request,
    crate: UploadFile = File(...),
    output_dir: str = Form(...),
    audio_format: str = Form("flac"),
    folder_template: str = Form(DEFAULT_TEMPLATE),
) -> HTMLResponse:
    raw = (await crate.read()).decode("utf-8", "replace")
    try:
        manifest = CrateManifest.from_json(raw)
    except Exception:
        return HTMLResponse(
            "<div class='err'>That file isn't a valid crate.json.</div>", status_code=400
        )
    settings = Settings(
        output_dir=Path(output_dir).expanduser(),
        audio_format=audio_format,
        folder_template=folder_template,
    )
    overrides = {entry.spotify_id: entry for entry in manifest.tracks}
    job = jobs.start(manifest.playlist_url, settings, runner_kwargs={"overrides": overrides})
    return _results(request, job)


@app.get("/runs/{job_id}", response_class=HTMLResponse)
def poll_run(request: Request, job_id: str) -> HTMLResponse:
    job = jobs.get(job_id)
    if job is None:
        return HTMLResponse("<div class='err'>run not found</div>", status_code=404)
    return _results(request, job)
