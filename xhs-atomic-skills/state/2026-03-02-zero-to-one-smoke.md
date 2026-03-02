# 2026-03-02 Zero to One Smoke

## Objective
Validate that the XHS pipeline can switch to a different book via a reusable skill with one command.

## New skill
- `xhs-book-reuse-smoke`
- Path: `xhs-atomic-skills/xhs-book-reuse-smoke/`

## Smoke command
```bash
python3 xhs-book-reuse-smoke/scripts/smoke_book_pipeline.py
```

## Run result
- Status: pass
- Run dir: `/Users/hy3/Desktop/setting/xhs-pipeline/products/skill-smokes/从0到1_smoke_20260302T015125Z`
- Cards: 10
- Dimensions: all `1080x1440`
- Manifest check: pass

## Winning defaults
- Keep deterministic direct renderer for smoke.
- Keep compact readability settings:
  - `font-scale=1.18`
  - `heading-scale=1.24`
  - `emphasis-scale=1.30`
  - `max-lines-per-block=2`
  - `max-chars-per-line=16`

## Risks / TODO
- Smoke currently starts from `book_outline.v1.json`; EPUB/PDF extraction stage is not included in this atomic skill.
- Add optional `--publish-dry-run` bridge later if needed.

---

## Persona continuation smoke (hard_thing_persona)

### Objective
Continue previous人物锚点方案 and confirm it is reusable as a stable preset, not a one-off manual operation.

### Command
```bash
python3 xhs-book-reuse-smoke/scripts/smoke_book_pipeline.py --preset hard_thing_persona
```

### Result
- Status: pass
- Run dir: `/Users/hy3/Desktop/setting/xhs-pipeline/products/skill-smokes/创业维艰the-hard-thing-about-hard-things_hard_thing_persona_smoke_20260302T020937Z`
- Hero anchor: `/Users/hy3/Desktop/setting/xhs-pipeline/references/author_ben_horowitz_anchor_real.png`
- Hero mode: `cover`
- Cards: 10
- Dimensions: all `1080x1440`
- Manifest check: pass
