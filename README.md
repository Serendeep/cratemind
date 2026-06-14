# cratemind

[![CI](https://github.com/Serendeep/cratemind/actions/workflows/ci.yml/badge.svg)](https://github.com/Serendeep/cratemind/actions/workflows/ci.yml)

Paste a Spotify playlist, get a folder of tracks sorted by genre and tempo.

cratemind downloads each song, works out its BPM and genre, and files it into
folders like `House/120-127bpm/`. It grabs lossless FLAC when it can and falls
back to a normal download when it can't. Everything runs on your own computer.
No website, no account, nothing uploaded.

---

## What you need first

cratemind relies on three free tools. You install each one once. Pick your
operating system and paste the commands into a terminal.

**1. uv** — runs cratemind

- macOS / Linux:
  ```
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- Windows (PowerShell):
  ```
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

**2. ffmpeg** — handles the audio

- macOS (Homebrew): `brew install ffmpeg`
- Windows (winget): `winget install Gyan.FFmpeg`
- Linux (apt): `sudo apt install ffmpeg`

**3. spotdl** — fetches the tracks

```
uv tool install spotdl
```

That's it. (Lossless FLAC needs one more optional tool — see
[Lossless downloads](#lossless-downloads). cratemind works fine without it.)

---

## Get cratemind

Download the project as a ZIP from its GitHub page (the green **Code** button →
**Download ZIP**) and unzip it, or clone it:

```
git clone https://github.com/Serendeep/cratemind.git
cd cratemind
```

---

## Easy setup (one command)

From the cratemind folder, run the setup script for your system. It installs uv,
ffmpeg, and spotdl (and points you to the manual download if it can't), then sets
up the app:

- macOS / Linux: `./setup.sh`
- Windows (PowerShell): `./setup.ps1`

Prefer to install by hand? The steps under "What you need first" are the manual
version.

---

## Run it

From the cratemind folder:

```
uv run cratemind
```

The first run takes a minute while uv sets things up. When it's ready it prints a
link — open `http://127.0.0.1:8000` in your browser. Paste a playlist link, pick
a folder, and hit **Run**.

---

## Using it

- **Output folder** — where your sorted music lands. Defaults to
  `~/Music/cratemind`.
- **Format** — FLAC (best quality) by default; MP3 and M4A are smaller.
- **Folder template** — how folders get named. `{genre}/{bpm_bucket}/` gives you
  `House/120-127bpm/`. You can mix and match these tokens: `{genre}`,
  `{bpm_bucket}`, `{bpm}`, `{key}`, `{artist}`, `{year}`. `{key}` is the Camelot
  code (like `8A`) for harmonic mixing, also shown next to each track's BPM.
- **Advanced** — the BPM window (used to correct half- or double-tempo
  mistakes) and how wide each tempo band is.

Tracks appear in a live list as they download, get analyzed, and get sorted.
Anything cratemind can't find a genre for goes into an `unsorted` folder, so
nothing ever gets lost.

Re-running the same playlist is cheap: cratemind keeps a hidden
`.cratemind-cache` folder inside your output folder with the original downloads,
so it skips anything it already has. You can delete that folder to reclaim space;
it just re-downloads next time.

---

## Sharing a crate

You can export a crate as a small `crate.json` file. It holds the analysis —
genre and BPM per track — not the audio. Someone else can import it to rebuild
the same sorted folders without re-analyzing anything. You can also upload it to
a free host (catbox.moe or 0x0.st) to get a link you can pass around.

---

## Lossless downloads

cratemind downloads in true lossless FLAC whenever it can, using
[SpotiFLAC](https://github.com/ShuShuzinhuu/SpotiFLAC-Module-Version), which the
setup script installs for you. When a track isn't available in lossless, it
quietly falls back to a standard-quality download. Nothing to configure.

---

## Troubleshooting

- **"spotdl is not installed"** — run `uv tool install spotdl`.
- **"ffmpeg not found"** — install ffmpeg (see above).
- **A BPM looks wrong (half or double)** — widen or narrow the BPM window under
  Advanced so it matches the music you're sorting.

---

## Contributing

Pull requests are welcome. To get set up:

1. Fork and clone the repo.
2. Install everything, including the test tools:
   ```
   uv sync --extra dev
   ```
3. Make your change. Keep modules small and add a test for any new behavior.
4. Run the tests — they should all pass before you open a PR:
   ```
   uv run pytest
   ```
5. Open a pull request that says what changed and why.

Keep commits focused and write clear, present-tense messages (for example,
`fix bpm rounding`). For anything large, open an issue first so we can talk it
through before you spend time on it.

---

## Reporting bugs

Open an issue on the [GitHub Issues page](https://github.com/Serendeep/cratemind/issues) and include:

- What you did — your format and template settings, and the playlist link if
  it's public.
- What you expected versus what actually happened.
- The error message, copied from the terminal.
- Your operating system and tool versions:
  ```
  uv --version
  ffmpeg -version
  spotdl --version
  ```

The more of that you include, the faster it gets fixed. For anything
security-sensitive, please contact the maintainer privately instead of opening a
public issue.

---

## A one-click app (coming soon)

A bundled version with everything inside (no terminal, no setup), code-signed so
it opens without security warnings, is planned for desktop. Pre-order for $50 to
lock in the early-supporter price and get it the day it ships. Look for the
pre-order link in the app footer, or [buy me a coffee](https://buymeacoffee.com/serendeep).

---

## Support

If cratemind saved you some time, you can
[buy me a coffee](https://buymeacoffee.com/serendeep). No pressure, it's free
either way.

---

## License and disclaimer

MIT — see [LICENSE](LICENSE).

Please read the [DISCLAIMER](DISCLAIMER.md). In short: cratemind is for
organizing music you're entitled to use, and you're responsible for following
Spotify's terms and copyright law where you live. It isn't affiliated with
Spotify or any other service.
