# TODOS

Deferred work with enough context to pick up cold. Add entries via review
sessions; delete them when shipped or consciously dropped.

## Parallel analysis workers for large-library scans

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
