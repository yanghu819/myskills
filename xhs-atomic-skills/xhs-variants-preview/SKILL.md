---
name: xhs-variants-preview
description: Generate and render multiple Xiaohongshu variants, then build preview sheets for side-by-side review. Use when users ask for 多版本预览, A/B/C/D style comparison, or first-card-only comparison.
---

# xhs-variants-preview

Use this skill to batch-produce preview-ready variants.

## Inputs
- Outline file
- Output root
- Variant set (`A,B,C,D` by default)
- Target cards (`10`)

## Workflow
1. Generate variant markdowns:
   - `python3 scripts/generate_xhs_variants.py --outline <json> --output-root <dir> --variants A,B,C,D --target-cards 10`
2. Render variants:
   - `bash scripts/render_xhs_variants.sh --variant-index <variant_index.json> --width 1080 --height 1440 --preview-mode all`
3. Build preview sheets:
   - `python3 scripts/build_preview_sheet.py ...`
4. Deliver compact preview first:
   - each variant first card + title
   - full 10-card sheet on demand

## Output
- `variants/<id>/xhs_post.<id>.md`
- `variants/<id>/rendered/01-card.png ... 10-card.png`
- `variants/<id>/preview_sheet.<id>.png`
- `variant_index.json`
