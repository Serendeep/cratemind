#!/usr/bin/env bash
# cratemind setup — installs uv, ffmpeg, and spotdl, then the app.
# Anything it can't install automatically, it points you to the download page.
set -uo pipefail

info() { printf '\033[0;36m> %s\033[0m\n' "$1"; }
ok()   { printf '\033[0;32mok %s\033[0m\n' "$1"; }
warn() { printf '\033[0;33m!! %s\033[0m\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# uv ------------------------------------------------------------------
if have uv; then
  ok "uv already installed"
else
  info "installing uv..."
  if curl -LsSf https://astral.sh/uv/install.sh | sh; then
    ok "uv installed"
  else
    warn "couldn't install uv automatically. Install it manually: https://docs.astral.sh/uv/getting-started/installation/"
  fi
  export PATH="$HOME/.local/bin:$PATH"
fi

# ffmpeg --------------------------------------------------------------
if have ffmpeg; then
  ok "ffmpeg already installed"
else
  info "installing ffmpeg..."
  if have brew; then brew install ffmpeg && ok "ffmpeg installed"
  elif have apt-get; then sudo apt-get update && sudo apt-get install -y ffmpeg && ok "ffmpeg installed"
  elif have dnf; then sudo dnf install -y ffmpeg && ok "ffmpeg installed"
  elif have pacman; then sudo pacman -S --noconfirm ffmpeg && ok "ffmpeg installed"
  else warn "no supported package manager found. Install ffmpeg manually: https://ffmpeg.org/download.html"
  fi
fi

# spotdl --------------------------------------------------------------
if have spotdl; then
  ok "spotdl already installed"
elif have uv; then
  info "installing spotdl..."
  uv tool install spotdl && ok "spotdl installed"
else
  warn "install uv first, then run: uv tool install spotdl  (docs: https://spotdl.github.io/spotify-downloader/)"
fi

# SpotiFLAC (optional — lossless FLAC) --------------------------------
# Non-standard packaging, so this is best-effort. cratemind falls back to
# spotdl if it isn't present.
if have spotiflac; then
  ok "SpotiFLAC already installed"
elif have uv; then
  info "installing SpotiFLAC (optional, for lossless)..."
  if uv tool install SpotiFLAC >/dev/null 2>&1 && have spotiflac; then
    ok "SpotiFLAC installed"
  else
    warn "Couldn't install SpotiFLAC. That's fine, cratemind will use standard-quality downloads instead."
  fi
fi

# cratemind -----------------------------------------------------------
if have uv; then
  info "installing cratemind..."
  uv sync && ok "cratemind ready"
fi

echo
ok "Done. Start cratemind with:  uv run cratemind"
echo "Then open http://127.0.0.1:8000 in your browser."
