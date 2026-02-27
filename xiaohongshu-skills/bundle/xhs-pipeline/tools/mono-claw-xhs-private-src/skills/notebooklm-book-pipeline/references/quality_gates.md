# Quality Gates

Use these checks before sending outputs downstream:

1. Split quality:
- Every part in `split_manifest.json` has `chars >= 8000` (unless source book itself is short).
- Part count is close to requested `--target-parts` (recommended deviation <= 2).
- Chapter titles are non-empty for each part.

2. NotebookLM ingestion quality:
- `source add` and `source wait` return success for each part.
- Failed parts are recorded in `run_manifest.json` with explicit errors.

3. Artifact quality:
- `report.md` exists per successful part.
- `quiz.json` and `flashcards.json` are valid JSON.
- If `video` is requested, output file exists and size > 1MB.

4. Recoverability:
- Re-run should be possible by reusing the same `split_manifest.json`.
- The pipeline output directory should contain `run_manifest.json` as a single source of truth.
