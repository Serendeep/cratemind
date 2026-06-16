#!/usr/bin/env bash
# cratemind setup: installs the tools cratemind needs, then the app itself.
# Walks through each step, shows the command it runs, and asks before the big
# optional download. Run with --yes to accept every default and skip prompts.
set -uo pipefail

# ---- colors (off when piped or NO_COLOR is set) ---------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  BOLD=$(printf '\033[1m');  DIM=$(printf '\033[2m');   RESET=$(printf '\033[0m')
  GREEN=$(printf '\033[38;5;114m'); CYAN=$(printf '\033[36m')
  YELLOW=$(printf '\033[33m'); RED=$(printf '\033[31m'); GREY=$(printf '\033[90m')
else
  BOLD=''; DIM=''; RESET=''; GREEN=''; CYAN=''; YELLOW=''; RED=''; GREY=''
fi

# ---- flags + interactivity ------------------------------------------------
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help)
      printf 'Usage: ./setup.sh [--yes]\n  --yes   accept defaults, no prompts\n'
      exit 0 ;;
  esac
done
INTERACTIVE=1
{ [ -t 0 ] && [ -e /dev/tty ]; } || INTERACTIVE=0

have() { command -v "$1" >/dev/null 2>&1; }

# ---- output helpers -------------------------------------------------------
STEP=0; TOTAL=5
step()  { STEP=$((STEP + 1)); printf '\n%s▸ [%d/%d] %s%s%s  %s%s\n' \
            "$BOLD$GREEN" "$STEP" "$TOTAL" "$RESET$BOLD" "$1" "$RESET" "$GREY$2" "$RESET"; }
run()   { printf '    %s$ %s%s\n' "$DIM" "$*" "$RESET"; "$@"; }
good()  { printf '    %s✓%s %s\n' "$GREEN" "$RESET" "$1"; }
skip()  { printf '    %s✓%s %s%s%s\n' "$GREEN" "$RESET" "$DIM" "$1" "$RESET"; }
warn()  { printf '    %s!%s %s\n' "$YELLOW" "$RESET" "$1"; }
fail()  { printf '    %s✗%s %s\n' "$RED" "$RESET" "$1"; }

# ask "question" default(Y|N) -> 0 for yes, 1 for no
ask() {
  local q="$1" def="${2:-Y}" ans hint='[Y/n]'
  [ "$def" = "N" ] && hint='[y/n]'
  if [ "$ASSUME_YES" = 1 ] || [ "$INTERACTIVE" = 0 ]; then
    [ "$def" = "Y" ]; return
  fi
  printf '    %s%s%s %s ' "$CYAN" "$q" "$RESET" "$hint" >/dev/tty
  read -r ans </dev/tty || ans=''
  ans="${ans:-$def}"
  case "$ans" in [Yy]*) return 0 ;; *) return 1 ;; esac
}

# ---- box drawing (padding measured in code points, so it stays aligned) ----
BOX_W=50
RULE=$(printf '─%.0s' $(seq 1 "$BOX_W"))
boxtop() { printf '%s   ╭%s╮%s\n' "$GREEN" "$RULE" "$RESET"; }
boxbot() { printf '%s   ╰%s╯%s\n' "$GREEN" "$RULE" "$RESET"; }
boxln()  {
  local s="${1:-}" n
  n=$(( BOX_W - 2 - ${#s} )); [ "$n" -lt 0 ] && n=0
  printf '%s   │%s %s%*s %s│%s\n' "$GREEN" "$RESET" "$s" "$n" '' "$GREEN" "$RESET"
}

# ---- banner ---------------------------------------------------------------
printf '\n'
boxtop
boxln ""
boxln "◉  cratemind"
boxln "   a Spotify playlist, sorted into crates"
boxln "   by genre and tempo"
boxln ""
boxbot
printf '\n'
printf '  This sets up four free tools and the app. Here is the plan:\n\n'
printf '    %s1.%s %suv%s        runs the app\n' "$GREEN" "$RESET" "$BOLD" "$RESET"
printf '    %s2.%s %sspotdl%s    fetches the tracks\n' "$GREEN" "$RESET" "$BOLD" "$RESET"
printf '    %s3.%s %sffmpeg%s    decodes the audio\n' "$GREEN" "$RESET" "$BOLD" "$RESET"
printf '    %s4.%s %scratemind%s the app and its dependencies\n' "$GREEN" "$RESET" "$BOLD" "$RESET"
printf '    %s5.%s %sgenre model%s  optional, reads genres from the audio (~330 MB)\n' "$GREEN" "$RESET" "$BOLD" "$RESET"
printf '\n'
printf '  Anything already installed is left as is. Nothing leaves your computer.\n'

if ! ask "Ready to start?" Y; then
  printf '\n  No changes made. Run %s./setup.sh%s again when you are ready.\n\n' "$BOLD" "$RESET"
  exit 0
fi

# ---- 1. uv ----------------------------------------------------------------
step "uv" "runs the app"
if have uv; then
  skip "already installed"
else
  printf '    Installing uv from astral.sh.\n'
  if run sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'; then
    good "uv installed"
  else
    fail "couldn't install uv. Install it by hand, then re-run:"
    warn "https://docs.astral.sh/uv/getting-started/installation/"
  fi
  export PATH="$HOME/.local/bin:$PATH"
fi

# ---- 2. spotdl ------------------------------------------------------------
# Installed before ffmpeg because the ffmpeg fallback below leans on spotdl's
# portable-ffmpeg downloader when no system package manager is available.
#
# Pin Python 3.12: on newer interpreters spotdl's dependencies fail with an
# "openssl outdated" error. The skip-guard checks that spotdl actually RUNS, not
# just that it exists, so a previously broken install gets force-reinstalled.
step "spotdl" "fetches the tracks"
if have spotdl && spotdl --version >/dev/null 2>&1; then
  skip "already installed"
elif have uv; then
  if run uv tool install --force --python 3.12 spotdl; then
    good "spotdl installed"
  else
    fail "spotdl install failed"
  fi
else
  fail "needs uv first. Re-run this script once uv is in place"
fi

# ---- cache detection ------------------------------------------------------
# Best-effort mirror of platformdirs.user_cache_dir("cratemind") for macOS/Linux.
# Used only to skip artifacts already on disk so re-runs (the no-git "download a
# fresh ZIP" update path) don't re-download. The Python side (genre/audio.py,
# ffmpeg.py) stays the source of truth for the real paths.
cratemind_cache() {
  case "$(uname -s)" in
    Darwin) printf '%s' "$HOME/Library/Caches/cratemind" ;;
    *)      printf '%s' "${XDG_CACHE_HOME:-$HOME/.cache}/cratemind" ;;
  esac
}
model_present() { ls "$(cratemind_cache)"/models/*.onnx >/dev/null 2>&1; }
ffmpeg_present() {
  have ffmpeg && return 0  # a system ffmpeg on PATH
  local bin
  for bin in "$(cratemind_cache)/bin/ffmpeg" "$HOME/.spotdl/ffmpeg" "$HOME/.config/spotdl/ffmpeg"; do
    [ -x "$bin" ] && return 0
  done
  return 1
}

# ---- 3. ffmpeg ------------------------------------------------------------
# System package manager first (a current ffmpeg on PATH); else spotdl's portable
# build. No PATH/symlink edits — the app finds the binary at runtime via
# cratemind.ffmpeg.ensure_ffmpeg_on_path and injects it into its own process.
step "ffmpeg" "decodes the audio"
if ffmpeg_present; then
  skip "already available"
else
  ffmpeg_done=0
  if   have brew;    then run brew install ffmpeg && ffmpeg_done=1
  elif have apt-get; then run sudo apt-get update; run sudo apt-get install -y ffmpeg && ffmpeg_done=1
  elif have dnf;     then run sudo dnf install -y ffmpeg && ffmpeg_done=1
  elif have pacman;  then run sudo pacman -S --noconfirm ffmpeg && ffmpeg_done=1
  fi

  if [ "$ffmpeg_done" = 1 ] && have ffmpeg; then
    good "ffmpeg installed"
  elif have spotdl && run spotdl --download-ffmpeg && ffmpeg_present; then
    good "ffmpeg installed (portable build; cratemind finds it automatically)"
  else
    fail "couldn't install ffmpeg automatically. Install it by hand, then re-run:"
    warn "https://ffmpeg.org/download.html"
  fi
fi

# ---- 4. cratemind ---------------------------------------------------------
step "cratemind" "the app and its dependencies"
WITH_AUDIO=0
if have uv; then
  if model_present; then
    # Genre detection already set up on a previous run; keep it. Syncing WITHOUT
    # the extra here would prune the audio deps and silently break it.
    WITH_AUDIO=1
    printf '    Genre detection is already set up; keeping it.\n'
    run uv sync --extra audio-genre && good "dependencies installed (with audio)"
  else
    printf '    Genre detection uses a local model. You can set it up now or skip it\n'
    printf '    and group tracks by artist until you add it later.\n'
    if ask "Set up genre detection? (downloads a ~330 MB model)" Y; then
      WITH_AUDIO=1
      run uv sync --extra audio-genre && good "dependencies installed (with audio)"
    else
      run uv sync && good "dependencies installed"
      warn "skipped the genre model. Add it later with: uv run cratemind download-model"
    fi
  fi
else
  fail "uv is missing, so the app can't be installed yet"
fi

# ---- 5. genre model -------------------------------------------------------
# download-model is idempotent (skips files already on disk), so a re-run after
# a fresh ZIP download reuses the cached ~330 MB model instead of re-fetching.
step "genre model" "reads genres from the audio"
if [ "$WITH_AUDIO" = 1 ] && have uv; then
  if model_present; then
    printf '    Already downloaded; reusing the cached model.\n'
  else
    printf '    Downloading the model (one time, ~330 MB).\n'
  fi
  run uv run cratemind download-model && good "genre model ready"
else
  skip "skipped (cratemind still sorts by tempo and groups by artist)"
fi

# ---- done -----------------------------------------------------------------
printf '\n'
boxtop
boxln "cratemind is ready"
boxln ""
boxln "start it:   uv run cratemind"
boxln "then open:  http://127.0.0.1:8000"
boxbot
printf '\n'
