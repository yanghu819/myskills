# XHS Book Pipeline (Local-First)

This folder implements a local-first pipeline for:

`EPUB/PDF -> structured outline JSON -> Markdown post -> 3:4 XHS cards (8-10) -> manual publish`

## What is included

- Fixed data contracts:
  - `contracts/book_outline.v1.json`
  - `contracts/xhs_post.v1.md`
  - `contracts/render_manifest.v1.json`
- Ready-to-run examples:
  - `examples/sample_book_outline.v1.json`
  - `examples/sample_xhs_post.v1.md`
- Tooling scripts:
  - `scripts/bootstrap_macos.sh`
  - `scripts/env_check.py`
  - `scripts/install_codex_skills.sh`
  - `scripts/pipeline_orchestrator.py`
  - `scripts/verify_offline.sh`
  - `scripts/setup_tools.sh`
  - `scripts/start_ebook_to_mindmap.sh`
  - `scripts/validate_book_outline.py`
  - `scripts/outline_to_xhs_md.py`
  - `scripts/render_xhs_cards.sh`
  - `scripts/build_render_manifest.py`
  - `scripts/run_pipeline.sh`
- Tests:
  - `tests/test_outline_to_xhs_md.py`
  - `tests/test_build_render_manifest.py`

## Quick start

1. Run environment check:

```bash
cd /Users/hy3/Desktop/setting/xhs-pipeline
python3 scripts/pipeline_orchestrator.py --stage check-env
```

2. Install runtime dependencies:

```bash
./scripts/bootstrap_macos.sh
```

3. Sync external tools:

```bash
./scripts/setup_tools.sh
```

4. Install Codex skills (primary + optional A/B):

```bash
./scripts/install_codex_skills.sh
```

5. Start the book parser UI:

```bash
./scripts/start_ebook_to_mindmap.sh
```

6. Create your `book_outline.v1.json` (use the contract template), then convert to Markdown:

```bash
python3 scripts/validate_book_outline.py --input /ABS/PATH/book_outline.v1.json
python3 scripts/outline_to_xhs_md.py \
  --input /ABS/PATH/book_outline.v1.json \
  --output /ABS/PATH/xhs_post.v1.md \
  --author "你的署名" \
  --target-cards 8
```

7. Render cards via `md-to-xhs-cards`:

```bash
./scripts/render_xhs_cards.sh \
  /ABS/PATH/xhs_post.v1.md \
  --width 1080 \
  --height 1440 \
  --author "你的署名"
```

Output folder defaults to `<markdown-dir>/<markdown-stem>-xhs-cards` and includes:

- `cover.png` + `card_*.png` (or `NN-card.png`, depending on renderer)
- `render_manifest.v1.json`

## Fixed card structure

Default is `8` cards:

1. Cover
2. Why this book matters
3. Insight 1
4. Insight 2
5. Insight 3
6. Case / evidence
7. Method steps
8. Action checklist (merged quote + CTA)

If target is `9`/`10`, quote and CTA are split into optional cards.

## Manual publish policy

Current implementation stops at rendering output for manual upload.
No auto-publish is wired in this version.

## Test

```bash
cd /Users/hy3/Desktop/setting/xhs-pipeline
python3 -m unittest discover -s tests -v
./scripts/verify_offline.sh
```

## Notes

- `md-to-xhs-cards` has been installed to:
  - `/Users/hy3/.codex/skills/md-to-xhs-cards`
- After new skill installs, restart Codex to pick up new skills.
- Reference analysis from `mono-claw-xhs`: `docs/MONO_CLAW_XHS_NOTES.md`

## Orchestrator Usage

Run common stages from a single command:

```bash
python3 scripts/pipeline_orchestrator.py --stage check-env
python3 scripts/pipeline_orchestrator.py --stage setup-tools
python3 scripts/pipeline_orchestrator.py --stage install-skills
python3 scripts/pipeline_orchestrator.py --stage build-sample-md --author "你的署名" --target-cards 8
python3 scripts/pipeline_orchestrator.py --stage verify-offline
```
