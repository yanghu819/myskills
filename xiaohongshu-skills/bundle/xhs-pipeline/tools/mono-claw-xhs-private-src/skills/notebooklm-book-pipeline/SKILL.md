---
name: notebooklm-book-pipeline
description: Split long books into NotebookLM-ready chunks and batch-generate per-part materials (report, quiz, flashcards, video) with reproducible manifests. Use when you need chapter-level decomposition, controlled source ingestion, and deterministic content packages for education, publishing, or paid knowledge products.
---

# NotebookLM Book Pipeline

Split a full book into high-signal parts, feed each part into NotebookLM as an independent source, and generate reusable material packs.

## Workflow

1. Split source book into parts:

```bash
python3 skills/notebooklm-book-pipeline/scripts/split_book_for_notebooklm.py \
  --book "/path/to/book.epub" \
  --target-parts 4 \
  --out-dir state/runtime/book_pipeline/hard-thing
```

This command creates:
- `chunks/*.md`
- `split_manifest.json`

2. Generate materials from NotebookLM:

```bash
python3 skills/notebooklm-book-pipeline/scripts/run_notebooklm_book_pipeline.py \
  --split-manifest state/runtime/book_pipeline/hard-thing/split_manifest.json \
  --notebook-id "<notebook_id>" \
  --artifacts report,quiz,flashcards,video \
  --output-dir state/runtime/book_pipeline/hard-thing/outputs
```

Re-run only failed parts:

```bash
python3 skills/notebooklm-book-pipeline/scripts/run_notebooklm_book_pipeline.py \
  --split-manifest state/runtime/book_pipeline/hard-thing/split_manifest.json \
  --notebook-id "<notebook_id>" \
  --artifacts report,quiz,flashcards \
  --part-ids P02,P03 \
  --rpc-retries 4
```

3. Test iteratively before real run:

```bash
python3 skills/notebooklm-book-pipeline/scripts/run_notebooklm_book_pipeline.py \
  --split-manifest state/runtime/book_pipeline/hard-thing/split_manifest.json \
  --notebook-id "<notebook_id>" \
  --artifacts report,quiz,flashcards \
  --limit-parts 1 \
  --dry-run
```

Use `--dry-run` first, then remove it for real generation.

## Output Contract

- Split step prints:
  - `RUN_ID`
  - `BOOK_TITLE`
  - `CHAPTERS`
  - `PARTS`
  - `OUT_DIR`
  - `MANIFEST`
- Pipeline step prints:
  - `RUN_ID`
  - `STATUS`
  - `NOTEBOOK_ID`
  - `PARTS_TOTAL`
  - `PARTS_FAILED`
  - `OUTPUT_DIR`
  - `RUN_MANIFEST`

Treat `run_manifest.json` as the single source of truth for per-part status.

## Operational Rules

- Keep each part around `12000` to `60000` chars by default; the splitter auto-widens upper bound when `--target-parts` is small.
- Use one source per part for better attribution and error isolation.
- Generate `report` first; add `video` only after report quality passes.
- On failures, rerun with `--limit-parts 1` for the failed part range.
- Prefer targeted retry with `--part-ids` and increased `--rpc-retries` when NotebookLM RPC is unstable.

## References

- Prompt patterns: `references/prompt_templates.md`
- Quality gates: `references/quality_gates.md`
