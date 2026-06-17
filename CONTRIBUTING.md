# Contributing to cratemind

Thanks for helping out. cratemind is a local FastAPI + HTMX app that downloads a
Spotify playlist, detects each track's BPM, key, and genre, and files the audio into
folders. This guide covers setup, the house rules, and how releases work.

## Setup

1. Fork and clone the repo.
2. Install everything, including the test tools:
   ```
   uv sync --extra dev
   ```
   `./setup.sh` (or `./setup.ps1`) sets up the full toolchain (spotdl, ffmpeg, and the
   app) from your clone, if you want the external CLIs too.
3. Run it from the clone:
   ```
   uv run cratemind
   ```

The external CLIs aren't Python deps. spotdl pins an old FastAPI, so it's installed as
an isolated tool: `uv tool install --force --python 3.12 spotdl`. ffmpeg is found at
runtime, so you never edit PATH.

## Making a change

- Keep modules small and focused, and add a test for any new behavior. Look at the
  existing `tests/test_*.py` for the style: dependency-injection fakes, no network.
- Inject dependencies as callables with real defaults (e.g. `tag_writer`, `fetch`,
  `estimator`) so tests pass fakes without patching.
- `Settings` is a frozen dataclass. Build copies with `.with_(...)`, never mutate.
- Degrade gracefully: tagging, the genre model, and the online fallback are best-effort.
  A failure there must not fail the sort. Don't swallow errors that matter, though.
- Before you open a PR, both of these should pass (CI runs them too):
  ```
  uv run pytest
  uv run ruff check src tests
  ```

## Good first issues

Small, self-contained, and a good way in:

- **Genre alias packs.** Map different names for one genre to a single folder. These
  live alongside `src/cratemind/genre/canonical.py` and are easy to review.
- **Folder-template tokens.** Add a new token to `src/cratemind/organize/template.py`.
- **New source backends.** The download path is one backend behind a shared pipeline;
  adding another follows the same shape.

See the [roadmap](docs/ROADMAP.md) for what's planned. Items there tagged
*Contributions welcome* are open to PRs now. For anything large, open an issue first so
we can talk it through before you spend time on it.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/), subject only:
`feat: …`, `fix: …`, `docs: …`, `chore: …`. Imperative, lowercase, no trailing period.
release-please parses the type, so it's load-bearing: `feat` bumps the minor version,
`fix` bumps the patch. Keep commits focused.

## Releasing (maintainers)

Releases are automated with
[release-please](https://github.com/googleapis/release-please). You don't tag or edit
the version by hand:

1. Merge your `feat:` / `fix:` work into `main`.
2. release-please opens (or updates) a **"chore(main): release X.Y.Z"** pull request
   that bumps the version in `pyproject.toml` and `__init__.py` and writes
   `CHANGELOG.md` from the commits since the last release.
3. Merge that release PR. release-please then tags `vX.Y.Z` and publishes a GitHub
   Release with the changelog. `cratemind update` and the installer reinstall from the
   new tag.

Version bumps follow the commit types: `fix:` patch, `feat:` minor, `feat!:` or
`BREAKING CHANGE:` major. Several unreleased commits collapse into one release PR, so
the version reflects the whole batch.

> One-time repo setting (already enabled): Settings → Actions → General → "Allow GitHub
> Actions to create and approve pull requests", which release-please needs to open its
> release PR.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By taking part,
you agree to uphold it.
