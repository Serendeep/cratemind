# cratemind one-line installer for Windows: installs the tools cratemind needs,
# then the app itself as a global `cratemind` command. Pulls the latest release.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Serendeep/cratemind/main/install.ps1 | iex"
#
# Unlike setup.ps1 (the from-a-clone path for contributors), this installs
# cratemind with `uv tool install`, so the command lands on PATH and there's no
# repo checkout to keep around. Re-run any time to upgrade to the latest release.
# Pass -Yes to accept every default and skip prompts.
param([switch]$Yes)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$Repo = 'Serendeep/cratemind'

function Have($c) { $null -ne (Get-Command $c -ErrorAction SilentlyContinue) }

# Best-effort mirror of platformdirs.user_cache_dir("cratemind") on Windows.
function Cratemind-Cache { Join-Path $env:LOCALAPPDATA "cratemind\cratemind\Cache" }
function Model-Present { Test-Path (Join-Path (Cratemind-Cache) "models\*.onnx") }
function Ffmpeg-Present {
  if (Have ffmpeg) { return $true }
  foreach ($b in @((Join-Path (Cratemind-Cache) "bin\ffmpeg.exe"),
                   (Join-Path $env:USERPROFILE ".spotdl\ffmpeg.exe"))) {
    if (Test-Path $b) { return $true }
  }
  return $false
}

# The tag of the latest published release, or $null if GitHub can't be reached.
function Latest-Tag {
  try {
    $r = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -ErrorAction Stop
    return $r.tag_name
  } catch { return $null }
}

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
Write-Host "  This installs four free tools and the app. Here is the plan:"
Write-Host ""
Write-Host "    1. uv        runs the app"
Write-Host "    2. spotdl    fetches the tracks"
Write-Host "    3. ffmpeg    decodes the audio"
Write-Host "    4. cratemind the app, as a global command"
Write-Host "    5. genre model  optional, reads genres from the audio (~330 MB)"
Write-Host ""
Write-Host "  Anything already installed is left as is. Nothing leaves your computer."

if (-not (Ask "Ready to start?" 'Y')) {
  Write-Host ""
  Write-Host "  No changes made. Run the installer again when you are ready."
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
}
# Put uv + its managed tools on PATH for the rest of this script (uv tool
# update-shell makes it permanent below).
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

# ---- 2. spotdl ------------------------------------------------------------
# Pin Python 3.12: newer interpreters surface an "openssl outdated" error from
# spotdl's deps. The guard checks spotdl actually RUNS, so a broken install gets
# replaced.
Step "spotdl" "fetches the tracks"
$spotdlOk = $false
if (Have spotdl) { spotdl --version *> $null; $spotdlOk = ($LASTEXITCODE -eq 0) }
if ($spotdlOk) {
  Skip "already installed"
} elseif (Have uv) {
  Cmd "uv tool install --force --python 3.12 spotdl"
  uv tool install --force --python 3.12 spotdl
  if ($LASTEXITCODE -eq 0) { Good "spotdl installed" } else { Fail "spotdl install failed" }
} else {
  Fail "needs uv first. Re-run this script once uv is in place"
}

# ---- 3. ffmpeg ------------------------------------------------------------
# winget first (a current ffmpeg on PATH); else spotdl's portable build. No PATH
# edits — the app finds the binary at runtime via ensure_ffmpeg_on_path.
Step "ffmpeg" "decodes the audio"
if (Ffmpeg-Present) {
  Skip "already available"
} elseif (Have winget) {
  Cmd "winget install Gyan.FFmpeg"
  try {
    winget install --silent --accept-package-agreements --accept-source-agreements Gyan.FFmpeg
    Good "ffmpeg installed"
  } catch {
    Fail "winget failed. Install ffmpeg by hand:"
    Warn "https://ffmpeg.org/download.html"
  }
} elseif (Have spotdl) {
  Cmd "spotdl --download-ffmpeg"
  spotdl --download-ffmpeg
  if (Ffmpeg-Present) { Good "ffmpeg installed (portable build; cratemind finds it automatically)" }
  else { Fail "couldn't fetch ffmpeg. Install it by hand:"; Warn "https://ffmpeg.org/download.html" }
} else {
  Fail "couldn't install ffmpeg automatically. Install it by hand:"
  Warn "https://ffmpeg.org/download.html"
}

# ---- 4. cratemind ---------------------------------------------------------
# Installed as a uv tool from the latest release tag, so `cratemind` lands on
# PATH. uv tool update-shell adds the tool bin dir to PATH for new terminals. The
# audio-genre extra is included only when genre detection is wanted.
Step "cratemind" "the app, as a global command"
$WithAudio = $false
if (Have uv) {
  $Tag = Latest-Tag
  if ([string]::IsNullOrWhiteSpace($Tag)) {
    Warn "couldn't reach GitHub for the latest release; installing from main"
    $Tag = "main"
  }

  if (Model-Present) {
    $WithAudio = $true
    Write-Host "    Genre detection is already set up; keeping it."
  } elseif (Ask "Set up genre detection? (downloads a ~330 MB model)" 'Y') {
    $WithAudio = $true
  }

  if ($WithAudio) {
    $Spec = "cratemind[audio-genre] @ git+https://github.com/$Repo@$Tag"
  } else {
    $Spec = "cratemind @ git+https://github.com/$Repo@$Tag"
  }

  Cmd "uv tool install --force `"$Spec`""
  uv tool install --force "$Spec"
  if ($LASTEXITCODE -eq 0) {
    Good "cratemind installed ($Tag)"
    uv tool update-shell *> $null
  } else {
    Fail "cratemind install failed"
  }
  if (-not $WithAudio) { Warn "skipped the genre model. Add it later with: cratemind download-model" }
} else {
  Fail "uv is missing, so the app can't be installed yet"
}

# ---- 5. genre model -------------------------------------------------------
# download-model is idempotent, so a re-run reuses the cached model.
Step "genre model" "reads genres from the audio"
if ($WithAudio -and (Have cratemind)) {
  if (Model-Present) { Write-Host "    Already downloaded; reusing the cached model." }
  else { Write-Host "    Downloading the model (one time, ~330 MB)." }
  Cmd "cratemind download-model"
  cratemind download-model
  if ($LASTEXITCODE -eq 0) { Good "genre model ready" } else { Fail "model download failed" }
} else {
  Skip "skipped (cratemind still sorts by tempo and groups by artist)"
}

# ---- done -----------------------------------------------------------------
Write-Host ""
Box-Top
Box-Line "cratemind is ready"
Box-Line ""
Box-Line "start it:   cratemind"
Box-Line "then open:  http://127.0.0.1:8000"
Box-Bot
Write-Host ""
Write-Host "  New terminal? If 'cratemind' is not found, open a fresh shell" -ForegroundColor DarkGray
Write-Host "  (uv added it to your PATH)." -ForegroundColor DarkGray
Write-Host ""
