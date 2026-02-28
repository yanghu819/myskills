---
name: xhs-direct-render
description: Render Xiaohongshu cards directly with large readable typography and component-based layout (1080x1440). Use when users request 大字、统一风格、避免小图不可读、direct rendering.
---

# xhs-direct-render

Use this skill for deterministic card rendering with strong mobile readability.

## Inputs
- Card markdown path
- Output directory
- Style params (font scale, heading scale, emphasis scale)

## Workflow
1. Run direct renderer:
   - `python3 scripts/render_xhs_cards_direct.py --input <md> --output <dir> --width 1080 --height 1440`
2. Apply typography defaults:
   - `--font-scale 1.22 --heading-scale 1.30 --emphasis-scale 1.36`
3. Validate:
   - exactly 10 cards
   - all images are `1080x1440`
   - no overflow/tiny-text risk in report
4. Return preview paths.
5. **Mandatory memory update**:
   - append run notes to `../state/YYYY-MM-DD-<topic>.md`
   - if defaults changed, update `../LEARNINGS.md`
   - commit + push to `main` immediately

## Design constraints
- No nested tiny screenshots.
- Key text must stay readable on phone first screen.
- Visual surprise allowed, but style must be globally consistent.
