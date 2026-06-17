# cratemind — notes for contributors (and Claude)

cratemind downloads a Spotify playlist, detects each track's BPM, key, and genre,
and files the audio into folders. It's a local FastAPI + HTMX app. End users
install it with the one-line `install.sh`/`install.ps1`, which `uv tool install`s
it as a global `cratemind` command; contributors run it from a clone with
`uv run cratemind`. Downloads happen through external CLIs (spotdl, SpotiFLAC);
analysis is local (librosa for BPM/key, an optional ONNX model for genre).

## Tooling

- **Python deps: `uv`** (not pip/poetry). `uv sync --extra dev` to set up; the app
  runs with `uv run cratemind`.
- **Lint: `ruff`** (`uv run ruff check src tests`). Config in `pyproject.toml`
  pins the rule set so a ruff upgrade can't break CI on its own.
- **Tests: `pytest`** (`uv run pytest`). CI runs lint then tests on every push/PR.
- **External CLIs are not Python deps.** spotdl pins an old FastAPI, so it's
  installed as an isolated tool: `uv tool install --force --python 3.12 spotdl`
  (newer Python triggers an openssl error in its deps). ffmpeg is found at runtime
  by `cratemind.ffmpeg.ensure_ffmpeg_on_path`, so users never edit PATH.

## Layout

- `download/` — backends (spotdl/SpotiFLAC via subprocess), tag reading, tag
  writing (`write_tags.py`).
- `analysis/` — BPM (`bpm.py`) and Camelot key (`key.py`).
- `genre/` — audio model, Deezer fallback, alias canonicalization.
- `organize/` — folder templating and the move (`sorter.py`).
- `pipeline.py` — per-track: analyze → resolve genre → sort → embed tags.
- `runner.py` — orchestrates a run, owns the store, emits per-track updates.
- `store/db.py` — SQLite (tracks, runs, settings, aliases).
- `web/` — FastAPI routes + Jinja/HTMX templates.
- `config.py` / `prefs.py` — `Settings` (frozen) and its JSON persistence.
- `ffmpeg.py`, `update.py` — runtime ffmpeg provisioning and self-update
  (`cratemind update` reinstalls the uv tool from the latest release tag).

## Conventions

- **`Settings` is a frozen dataclass.** Build copies with `.with_(...)`; never
  mutate. Persisted fields go in `prefs.load_settings`/`save_settings`. (Exception:
  `aliases` is a runtime carrier filled from the store per run, not persisted.)
- **Inject dependencies as callables with real defaults** (e.g. `tag_writer`,
  `fetch`, `estimator`), so tests pass fakes without patching.
- **Degrade gracefully.** Tagging, the genre model, and the online fallback are
  best-effort: a failure there must not fail the sort. Don't swallow errors that
  matter, though.
- Small, focused files. Add a test for new behaviour.

## How we work

Run `./scripts/setup-dev.sh` once after cloning — it installs dev deps and turns
on the git hooks (`commit-msg` enforces Conventional Commits; `pre-push` runs
ruff + pytest). Then:

1. Branch off `main` (`feat/...`, `fix/...`).
2. **Test first.** Write a failing test, then the code (see existing
   `tests/test_*.py` for the style — DI fakes, no network).
3. `uv run ruff check src tests && uv run pytest` both green.
4. Open a PR; CI must pass. Reviews (including Copilot) get addressed before merge.
5. Squash-merge feature PRs.

## Commits and releases

- **Conventional Commits, subject only**: `feat: …`, `fix: …`, `docs: …`,
  `chore: …`. Imperative, lowercase, no trailing period. release-please parses
  the type, so it's load-bearing — `feat` bumps minor, `fix` bumps patch.
- **Releases are automated** (release-please). Merge work to `main`; release-please
  opens a "chore(main): release X.Y.Z" PR that bumps the version and writes
  `CHANGELOG.md`. Merge that PR to tag `vX.Y.Z` and publish the GitHub Release,
  which `cratemind update` pulls. See README → Contributing → Releasing.
- One repo setting makes this work (already on): Settings → Actions → "Allow
  GitHub Actions to create and approve pull requests".

## Caches (outside the repo)

`platformdirs` user cache holds the genre model and ffmpeg
(`user_cache_dir("cratemind")`); user data holds prefs + the SQLite DB. Updates
and fresh-ZIP re-installs reuse these, so the heavy downloads happen once.
