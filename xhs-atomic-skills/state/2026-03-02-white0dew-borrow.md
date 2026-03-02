# 2026-03-02 white0dew borrow log

## Objective
- Review `white0dew/XiaohongshuSkills` and absorb reusable engineering patterns.

## What was borrowed
- Added reusable `run_lock.py` into `xhs-pipeline/scripts/`.
- Enabled single-instance guard for:
  - `run_red_blue_mimic.py`
  - `generate_xhs_variants.py`
  - `download_xhs_profile_archive.py`
  - `download_xhs_profile_full.py`

## Why it matters
- Prevents accidental concurrent runs from clobbering shared outputs / browser-bound jobs.
- Gives deterministic operator feedback and explicit exit code on conflicts.

## Validation
- `python3 -m py_compile` passed for all touched scripts.
- `--help` contract checks passed for all touched scripts.

## Next defaults
- Add login cache TTL helper for repeated account operations.
- Normalize ops scripts to structured JSON envelopes for downstream automation.
