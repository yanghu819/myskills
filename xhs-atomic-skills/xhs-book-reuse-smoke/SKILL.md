---
name: xhs-book-reuse-smoke
description: Run a reusable book-swap smoke pipeline for Xiaohongshu cards from outline to evidence assets, markdown, 10-card render, and manifest validation, including optional persona anchor rendering. Use when users ask whether the pipeline can quickly switch books, keep a人物锚点 style, want a new-book dry run, or request 冒烟验证 like 《从0到1》.
---

# xhs-book-reuse-smoke

Use this skill to verify that the XHS pipeline is reusable for a different book without changing core scripts.

## Inputs
- `--preset`: `zero_to_one` or `hard_thing_persona` (default `zero_to_one`)
- `--outline`: `book_outline.v1.json` path (optional; overrides preset default)
- `--author`: author signature for cards
- `--output-root`: run output root directory
- `--theme`: direct renderer theme (`editorial_unified_v1` default)
- `--hero-anchor`: optional author/persona image path
- `--hero-anchor-mode`: `cover|all|none`

## Default command

```bash
python3 scripts/smoke_book_pipeline.py \
  --preset zero_to_one \
  --outline references/zero_to_one.book_outline.v1.json \
  --author "Hy3" \
  --theme editorial_unified_v1
```

### Persona smoke command (继续之前人物)

```bash
python3 scripts/smoke_book_pipeline.py \
  --preset hard_thing_persona \
  --author "Hy3"
```

## Workflow
1. Validate outline schema (`book_outline.v1.json`).
2. Build large-text evidence assets (`evidence_01..06.png`).
3. Generate `xhs_post.v2.md` (fixed 10-card structure).
4. Render direct cards (`1080x1440`, optional persona anchor).
5. Build and verify `render_manifest.v1.json`.
6. Emit `smoke_report.json` with stage logs and pass/fail summary.

## Output contract
- `<run_dir>/xhs_post.zero_to_one.v2.md`
- `<run_dir>/assets/evidence_01.png ... evidence_06.png`
- `<run_dir>/rendered/01-card.png ... 10-card.png`
- `<run_dir>/rendered/render_manifest.v1.json`
- `<run_dir>/smoke_report.json`

## Quality gates (hard fail)
- Rendered card count must be `10`.
- Every card must be exactly `1080x1440`.
- Manifest `card_count` and image filenames must match actual files.
- If persona mode is enabled, report must include `hero_anchor_exists=true` (or explicit warning).

## Notes
- This skill does not publish notes; it is smoke-only.
- Works for Codex and Claude Code because all steps are plain CLI scripts.
- When smoke fails, inspect `<run_dir>/logs/*.log` first.
