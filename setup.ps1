# cratemind setup for Windows — installs uv, ffmpeg, and spotdl, then the app.
# Anything it can't install automatically, it points you to the download page.

function Have($cmd) { $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue) }
function Info($m) { Write-Host "> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "ok $m" -ForegroundColor Green }
function Warn($m) { Write-Host "!! $m" -ForegroundColor Yellow }

# uv
if (Have uv) {
  Ok "uv already installed"
} else {
  Info "installing uv..."
  try {
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    Ok "uv installed"
  } catch {
    Warn "couldn't install uv automatically. Install it manually: https://docs.astral.sh/uv/getting-started/installation/"
  }
}

# ffmpeg
if (Have ffmpeg) {
  Ok "ffmpeg already installed"
} elseif (Have winget) {
  Info "installing ffmpeg..."
  try {
    winget install --silent --accept-package-agreements --accept-source-agreements Gyan.FFmpeg
    Ok "ffmpeg installed"
  } catch {
    Warn "winget failed. Install ffmpeg manually: https://ffmpeg.org/download.html"
  }
} else {
  Warn "winget not found. Install ffmpeg manually: https://ffmpeg.org/download.html"
}

# spotdl
if (Have spotdl) {
  Ok "spotdl already installed"
} elseif (Have uv) {
  Info "installing spotdl..."
  uv tool install spotdl
  Ok "spotdl installed"
} else {
  Warn "install uv first, then run: uv tool install spotdl  (docs: https://spotdl.github.io/spotify-downloader/)"
}

# cratemind
if (Have uv) {
  Info "installing cratemind..."
  uv sync
  Ok "cratemind ready"
}

Write-Host ""
Ok "Done. Start cratemind with:  uv run cratemind"
Write-Host "Then open http://127.0.0.1:8000 in your browser."
