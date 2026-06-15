# cratemind setup for Windows: installs the tools cratemind needs, then the app.
# Walks through each step, shows the command it runs, and asks before the big
# optional download. Run with -Yes to accept every default and skip prompts.
param([switch]$Yes)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

function Have($c) { $null -ne (Get-Command $c -ErrorAction SilentlyContinue) }

# ---- box drawing ----------------------------------------------------------
$BoxW = 50
$Rule = ('─' * $BoxW)
function Box-Top { Write-Host ("   ╭" + $Rule + "╮") -ForegroundColor Green }
function Box-Bot { Write-Host ("   ╰" + $Rule + "╯") -ForegroundColor Green }
function Box-Line($s) {
  if ($null -eq $s) { $s = "" }
  $n = $BoxW - 2 - $s.Length
  if ($n -lt 0) { $n = 0 }
  Write-Host "   │ " -ForegroundColor Green -NoNewline
  Write-Host ($s + (' ' * $n) + " ") -NoNewline
  Write-Host "│" -ForegroundColor Green
}

# ---- step + status helpers ------------------------------------------------
$script:Step = 0
$Total = 5
function Step($name, $desc) {
  $script:Step++
  Write-Host ""
  Write-Host ("▸ [{0}/{1}] " -f $script:Step, $Total) -ForegroundColor Green -NoNewline
  Write-Host $name -NoNewline
  Write-Host ("  " + $desc) -ForegroundColor DarkGray
}
function Good($m) { Write-Host "    ✓ " -ForegroundColor Green  -NoNewline; Write-Host $m }
function Skip($m) { Write-Host "    ✓ " -ForegroundColor Green  -NoNewline; Write-Host $m -ForegroundColor DarkGray }
function Warn($m) { Write-Host "    ! " -ForegroundColor Yellow -NoNewline; Write-Host $m }
function Fail($m) { Write-Host "    ✗ " -ForegroundColor Red    -NoNewline; Write-Host $m }
function Cmd($m)  { Write-Host ("    $ " + $m) -ForegroundColor DarkGray }

function Ask($q, $def = 'Y') {
  if ($Yes) { return ($def -eq 'Y') }
  $hint = if ($def -eq 'Y') { '[Y/n]' } else { '[y/N]' }
  Write-Host ("    " + $q + " " + $hint + " ") -ForegroundColor Cyan -NoNewline
  $a = Read-Host
  if ([string]::IsNullOrWhiteSpace($a)) { $a = $def }
  return ($a -match '^[Yy]')
}

# ---- banner ---------------------------------------------------------------
Write-Host ""
Box-Top
Box-Line ""
Box-Line "◉  cratemind"
Box-Line "   a Spotify playlist, sorted into crates"
Box-Line "   by genre and tempo"
Box-Line ""
Box-Bot
Write-Host ""
Write-Host "  This sets up four free tools and the app. Here is the plan:"
Write-Host ""
Write-Host "    1. uv        runs the app"
Write-Host "    2. ffmpeg    decodes the audio"
Write-Host "    3. spotdl    fetches the tracks"
Write-Host "    4. cratemind the app and its dependencies"
Write-Host "    5. genre model  optional, reads genres from the audio (~344 MB)"
Write-Host ""
Write-Host "  Anything already installed is left as is. Nothing leaves your computer."

if (-not (Ask "Ready to start?" 'Y')) {
  Write-Host ""
  Write-Host "  No changes made. Run .\setup.ps1 again when you are ready."
  Write-Host ""
  exit 0
}

# ---- 1. uv ----------------------------------------------------------------
Step "uv" "runs the app"
if (Have uv) {
  Skip "already installed"
} else {
  Write-Host "    Installing uv from astral.sh."
  Cmd "irm https://astral.sh/uv/install.ps1 | iex"
  try {
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    Good "uv installed"
  } catch {
    Fail "couldn't install uv. Install it by hand, then re-run:"
    Warn "https://docs.astral.sh/uv/getting-started/installation/"
  }
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# ---- 2. ffmpeg ------------------------------------------------------------
Step "ffmpeg" "decodes the audio"
if (Have ffmpeg) {
  Skip "already installed"
} elseif (Have winget) {
  Cmd "winget install Gyan.FFmpeg"
  try {
    winget install --silent --accept-package-agreements --accept-source-agreements Gyan.FFmpeg
    Good "ffmpeg installed"
  } catch {
    Fail "winget failed. Install ffmpeg by hand:"
    Warn "https://ffmpeg.org/download.html"
  }
} else {
  Fail "winget not found. Install ffmpeg by hand:"
  Warn "https://ffmpeg.org/download.html"
}

# ---- 3. spotdl ------------------------------------------------------------
Step "spotdl" "fetches the tracks"
if (Have spotdl) {
  Skip "already installed"
} elseif (Have uv) {
  Cmd "uv tool install spotdl"
  uv tool install spotdl
  if ($LASTEXITCODE -eq 0) { Good "spotdl installed" } else { Fail "spotdl install failed" }
} else {
  Fail "needs uv first. Re-run this script once uv is in place"
}

# ---- 4. cratemind ---------------------------------------------------------
Step "cratemind" "the app and its dependencies"
$WithAudio = $false
if (Have uv) {
  Write-Host "    Genre detection uses a local model. You can set it up now or skip it"
  Write-Host "    and group tracks by artist until you add it later."
  if (Ask "Set up genre detection? (downloads a ~344 MB model)" 'Y') {
    $WithAudio = $true
    Cmd "uv sync --extra audio-genre"
    uv sync --extra audio-genre
    if ($LASTEXITCODE -eq 0) { Good "dependencies installed (with audio)" } else { Fail "uv sync failed" }
  } else {
    Cmd "uv sync"
    uv sync
    if ($LASTEXITCODE -eq 0) { Good "dependencies installed" } else { Fail "uv sync failed" }
    Warn "skipped the genre model. Add it later with: uv run cratemind download-model"
  }
} else {
  Fail "uv is missing, so the app can't be installed yet"
}

# ---- 5. genre model -------------------------------------------------------
Step "genre model" "reads genres from the audio"
if ($WithAudio -and (Have uv)) {
  Write-Host "    Downloading the model (one time, ~344 MB)."
  Cmd "uv run cratemind download-model"
  uv run cratemind download-model
  if ($LASTEXITCODE -eq 0) { Good "genre model ready" } else { Fail "model download failed" }
} else {
  Skip "skipped (cratemind still sorts by tempo and groups by artist)"
}

# ---- done -----------------------------------------------------------------
Write-Host ""
Box-Top
Box-Line "cratemind is ready"
Box-Line ""
Box-Line "start it:   uv run cratemind"
Box-Line "then open:  http://127.0.0.1:8000"
Box-Bot
Write-Host ""
