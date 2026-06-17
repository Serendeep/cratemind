#!/usr/bin/env sh
# cratemind one-line installer: installs the tools cratemind needs, then the app
# itself as a global `cratemind` command. Pulls the latest published release.
#
#   curl -fsSL https://raw.githubusercontent.com/Serendeep/cratemind/main/install.sh | sh
#
# Unlike setup.sh (the from-a-clone path for contributors), this installs
# cratemind with `uv tool install`, so the command lands on PATH and there's no
# repo checkout to keep around. Re-run any time to upgrade to the latest release.
# Pass --yes to accept every default and skip prompts.
set -u

REPO="Serendeep/cratemind"

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
      printf 'Usage: install.sh [--yes]\n  --yes   accept defaults, no prompts\n'
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
  q="$1"; def="${2:-Y}"; hint='[Y/n]'
  [ "$def" = "N" ] && hint='[y/N]'
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
  s="${1:-}"
  n=$(( BOX_W - 2 - ${#s} )); [ "$n" -lt 0 ] && n=0
  printf '%s   │%s %s%*s %s│%s\n' "$GREEN" "$RESET" "$s" "$n" '' "$GREEN" "$RESET"
}

# ---- release lookup -------------------------------------------------------
# The tag of the latest published release, or empty if GitHub can't be reached.
# The empty case is handled below by falling back to the default branch — useful
# when the unauthenticated API is rate-limited (60/hr) but the git endpoint, which
# uv uses to install, still works. A truly offline machine fails at the install.
latest_tag() {
  curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
    | grep '"tag_name"' | head -1 \
    | sed -E 's/.*"tag_name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/'
}

# ---- cache detection (mirror platformdirs; skip artifacts already on disk) --
cratemind_cache() {
  case "$(uname -s)" in
    Darwin) printf '%s' "$HOME/Library/Caches/cratemind" ;;
    *)      printf '%s' "${XDG_CACHE_HOME:-$HOME/.cache}/cratemind" ;;
  esac
}
model_present() { ls "$(cratemind_cache)"/models/*.onnx >/dev/null 2>&1; }
ffmpeg_present() {
  have ffmpeg && return 0
  for bin in "$(cratemind_cache)/bin/ffmpeg" "$HOME/.spotdl/ffmpeg" "$HOME/.config/spotdl/ffmpeg"; do
    [ -x "$bin" ] && return 0
  done
  return 1
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
printf '  This installs four free tools and the app. Here is the plan:\n\n'
printf '    %s1.%s %suv%s        runs the app\n' "$GREEN" "$RESET" "$BOLD" "$RESET"
printf '    %s2.%s %sspotdl%s    fetches the tracks\n' "$GREEN" "$RESET" "$BOLD" "$RESET"
printf '    %s3.%s %sffmpeg%s    decodes the audio\n' "$GREEN" "$RESET" "$BOLD" "$RESET"
printf '    %s4.%s %scratemind%s the app, as a global command\n' "$GREEN" "$RESET" "$BOLD" "$RESET"
printf '    %s5.%s %sgenre model%s  optional, reads genres from the audio (~330 MB)\n' "$GREEN" "$RESET" "$BOLD" "$RESET"
printf '\n'
printf '  Anything already installed is left as is. Nothing leaves your computer.\n'

if ! ask "Ready to start?" Y; then
  printf '\n  No changes made. Run the installer again when you are ready.\n\n'
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
fi
# uv installs both itself and the tools it manages here; put it on PATH for the
# rest of this script (uv tool update-shell makes it permanent below).
export PATH="$HOME/.local/bin:$PATH"

# ---- 2. spotdl ------------------------------------------------------------
# Pin Python 3.12: on newer interpreters spotdl's dependencies fail with an
# "openssl outdated" error. The guard checks spotdl actually RUNS, not just that
# it exists, so a previously broken install gets force-reinstalled.
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
# Installed as a uv tool from the latest release tag, so `cratemind` lands on
# PATH. `uv tool update-shell` adds the tool bin dir to the shell profile so the
# command works in new terminals. The audio-genre extra (onnxruntime + librosa)
# is included only when genre detection is wanted.
step "cratemind" "the app, as a global command"
WITH_AUDIO=0
if have uv; then
  TAG=$(latest_tag)
  if [ -z "$TAG" ]; then
    warn "couldn't reach GitHub for the latest release; installing from main"
    TAG="main"
  fi

  if model_present; then
    # Genre detection was set up before; keep the audio stack so it stays working.
    WITH_AUDIO=1
    printf '    Genre detection is already set up; keeping it.\n'
  elif ask "Set up genre detection? (downloads a ~330 MB model)" Y; then
    WITH_AUDIO=1
  fi

  if [ "$WITH_AUDIO" = 1 ]; then
    SPEC="cratemind[audio-genre] @ git+https://github.com/$REPO@$TAG"
  else
    SPEC="cratemind @ git+https://github.com/$REPO@$TAG"
  fi

  if run uv tool install --force "$SPEC"; then
    good "cratemind installed ($TAG)"
    run uv tool update-shell >/dev/null 2>&1
  else
    fail "cratemind install failed"
  fi
  [ "$WITH_AUDIO" = 1 ] || warn "skipped the genre model. Add it later with: cratemind download-model"
else
  fail "uv is missing, so the app can't be installed yet"
fi

# ---- 5. genre model -------------------------------------------------------
# download-model is idempotent (skips files already on disk), so a re-run reuses
# the cached ~330 MB model instead of re-fetching.
step "genre model" "reads genres from the audio"
if [ "$WITH_AUDIO" = 1 ] && have cratemind; then
  if model_present; then
    printf '    Already downloaded; reusing the cached model.\n'
  else
    printf '    Downloading the model (one time, ~330 MB).\n'
  fi
  run cratemind download-model && good "genre model ready"
else
  skip "skipped (cratemind still sorts by tempo and groups by artist)"
fi

# ---- done -----------------------------------------------------------------
printf '\n'
boxtop
boxln "cratemind is ready"
boxln ""
boxln "start it:   cratemind"
boxln "then open:  http://127.0.0.1:8000"
boxbot
printf '\n'
printf '  %sNew terminal?%s If `cratemind` is not found, open a fresh shell\n' "$DIM" "$RESET"
printf '  (uv added it to your PATH) or run: %sexport PATH="$HOME/.local/bin:$PATH"%s\n\n' "$BOLD" "$RESET"
