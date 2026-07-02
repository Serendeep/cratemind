# TODOS

Deferred work with enough context to pick up cold. Grouped by component,
prioritized P0 (urgent) through P4 (someday). Shipped items move to Completed.

## Download / staging

### Verify spotdl scan semantics under per-run staging

- **Priority:** P1
- **What:** Confirm with a live spotdl run whether `--scan-for-songs` still
  finds already-sorted files now that downloads stage into
  `output_dir/.staging/<run_id>/` instead of the output root.
- **Why:** If the scan is rooted at the output template's directory, a re-run
  of a fully sorted crate re-downloads the entire playlist (bandwidth + time).
  The stranding half is already fixed (staged duplicates of sorted tracks are
  deleted, `tests/test_runner.py::test_rerun_deletes_staged_duplicates_of_sorted_tracks`),
  so the open question is purely download cost.
- **Context (2026-07-02):** flagged by the ship adversarial review; needs
  spotdl installed and a real playlist to verify. If the scan misses sorted
  files, consider passing the output root to `--scan-for-songs` explicitly or
  seeding staging with hardlinks before the run.

## Pipeline / analysis

### Parallel analysis workers for large-library scans

- **Priority:** P2
- **What:** Analyze N tracks concurrently in `runner.run_crate`'s per-track loop
  (librosa BPM/key + ONNX genre are the cost; a worker pool divides wall-clock).
- **Why:** A first preview of a 500-file local library is hours today — the
  pipeline is strictly sequential. The dry-run design doc ships with honest
  "hours for big libraries" copy; this is the fix behind the disclaimer.
- **Pros:** First-scan time drops toward 1/N; the preview→apply flow already
  isolates the side effects (apply is a separate, cheap pass), so analysis is
  the safe part to parallelize.
- **Cons:** Concurrency in the pipeline is real complexity: per-track store
  commits, `on_update` ordering for the UI, `_PLACE_LOCK` contention on
  non-preview runs. ONNX/librosa already use multiple cores per track, so the
  win is < Nx — measure before assuming.
- **Context (2026-07-02):** `runner.py` processes `new_tracks` in a plain loop;
  `store/db.py` commits per upsert; the web layer polls `job.tracks` guarded by
  `job.lock`, so out-of-order updates render fine. Start by pooling only the
  analysis (BPM/key/genre/quality) and keep sort/move sequential.
- **Depends on / blocked by:** best after the local-folder source (issue #11)
  ships, so the optimization targets a real flow.

## Web

### Apply a preview by run id, not job id

- **Priority:** P2
- **What:** An apply route keyed by `run_id` (crates page) instead of the
  in-memory `job_id`, plus an Apply button on the crates list for runs with
  previewed rows.
- **Why:** The store durably holds everything apply needs, but after a server
  restart the only path to those files today is Re-run (which correctly forces
  a fresh preview). A user who previews, closes the laptop, and comes back
  must re-preview instead of applying what they already approved.
- **Context (2026-07-02):** flagged by the ship adversarial review. The crates
  list already shows previewed counts; `apply_crate` already takes a run_url.

## Organize / sorter

### Normalize the in-place path check before local-folder sorting ships

- **Priority:** P2
- **What:** `sort_track`'s already-in-place check compares paths textually
  while the escape guard resolves; symlinked or case-differing paths (macOS)
  dodge the in-place branch and get suffix-renamed on apply.
- **Why:** Unreachable today (downloads never sit at their destination via
  symlink), but the local-folder source (issue #11) points at arbitrary user
  folders where this happens.
- **Context (2026-07-02):** compare via `Path.resolve()` on both sides or
  `os.path.samefile` when both exist. Belongs in the PR 2 branch.

## Completed

(nothing yet — entries move here with `**Completed:** vX.Y.Z (YYYY-MM-DD)`)
