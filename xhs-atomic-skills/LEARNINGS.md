# xhs-atomic-skills Learnings

## Update Policy (Mandatory)

- Every production iteration must write one run log under `state/` before publish.
- Every run log must include: objective, winning decisions, failed decisions, next defaults.
- When a decision repeatedly wins (>=2 runs), promote it into the corresponding `SKILL.md` default.
- Commit message must include `xhs-learnings:` prefix when learnings are updated.

## Stable Defaults (2026-02-28)

### Copy

- Use conversion-first rhythm for business/self-growth notes:
  - identity hook -> pain diagnosis -> contrarian truths -> case -> anti-myth -> 3 steps -> action checklist -> CTA
- One card = one conclusion + one action sentence.
- First card must answer in 0.3s: for whom + what pain + what immediate gain.
- Avoid absolute promises (`100%`, `唯一`, `暴富`, `闭眼冲`).

### Visual

- For Xiaohongshu 3:4 cards, readability is primary:
  - large heading, short line length, strict line cap.
- Prefer unified component system over decorative variety:
  - title block, emphasis strip, evidence panel, checklist, divider.
- Ban tiny nested infographics that become unreadable on mobile.

### Rendering

- Keep deterministic rendering path with direct renderer for final delivery.
- Recommended baseline for dense Chinese copy:
  - `--max-chars-per-line 16`
  - `--max-lines-per-block 2`
  - moderate scale (`font 1.14-1.18`, `heading 1.20-1.24`, `emphasis 1.24-1.30`).
- If overflow appears, shorten copy first, then adjust scale.

### Quality Gates

- 10 images exactly, all `1080x1440`.
- No line overflow, no tiny-text risk.
- Card 9 must be checklist style (`- [ ]`).
- Card 10 must contain executable CTA (tonight action + tomorrow review).

## Reusable Book Swap (2026-03-02)

- To validate pipeline portability for a new book, prefer one deterministic smoke command over manual multi-command runs.
- Stable smoke sequence:
  1. validate outline
  2. build compact evidence assets
  3. generate `xhs_post.v2.md`
  4. direct render 10 cards
  5. manifest + dimension verification
- Recommended readability defaults for smoke:
  - `font-scale=1.18`
  - `heading-scale=1.24`
  - `emphasis-scale=1.30`
  - `max-lines-per-block=2`
  - `max-chars-per-line=16`

## Persona Anchors (2026-03-02)

- Keep persona rendering as an explicit smoke preset instead of ad-hoc flags.
- Stable founder-cover defaults:
  - `preset=hard_thing_persona`
  - `theme=editorial_unified_v1`
  - `hero-anchor-mode=cover`
- If anchor file is missing, continue render in no-anchor mode and emit warning (do not hard-fail smoke).

## Ops Stability Borrow (2026-03-02)

- Borrowed from `white0dew/XiaohongshuSkills`:
  - single-instance lock is a high ROI baseline for all long-running XHS scripts.
- Promoted default:
  - all high-frequency scripts must guard with `single_instance(...)` and return a clear lock-conflict exit code.
- First rollout covered:
  - `run_red_blue_mimic.py`
  - `generate_xhs_variants.py`
  - `download_xhs_profile_archive.py`
  - `download_xhs_profile_full.py`
- Next recommended borrow:
  - unified CDP ops command taxonomy (`check-login/search/detail/comment/content-data`)

## Ops Stability Borrow v2 (2026-03-02)

- Implemented `xhs_ops_common.py` shared helper:
  - positive login cache (`--login-cache-ttl-hours`, default 12h)
  - lightweight session verification + fallback on transient request errors
  - shared CSV writer
- Added structured machine-readable output:
  - `DOWNLOAD_PROFILE_ARCHIVE_RESULT`
  - `DOWNLOAD_PROFILE_FULL_RESULT`
  - `GENERATE_XHS_VARIANTS_RESULT`
  - `RUN_RED_BLUE_MIMIC_RESULT`
- Added optional output contracts:
  - `--csv-file` for profile archive/full index export
  - `--result-json` for redblue/variants payload export
