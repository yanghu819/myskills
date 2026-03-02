---
name: xhs-cdp-ops
description: Reusable CDP-style Xiaohongshu operations patterns for archive/publish/search workflows, with runtime safety guards (single-instance lock) and smoke checks. Use when users ask to stabilize XHS automation, add ops-grade CLI flows, or benchmark against repos like white0dew/XiaohongshuSkills.
---

# xhs-cdp-ops

This skill captures operational patterns learned from production-style XHS CDP tools and applies them to our local pipeline with safe defaults.

## What this skill focuses on

- Runtime safety:
  - single-instance lock to prevent concurrent script collisions
  - clear exit code `3` for lock conflicts
- CLI discipline:
  - consistent `--help` contracts
  - predictable script entry points
- Ops workflow:
  - profile archive pipeline checks
  - render/copy iteration command sanity checks

## Local scripts covered

- `/Users/hy3/Desktop/setting/xhs-pipeline/scripts/run_lock.py`
- `/Users/hy3/Desktop/setting/xhs-pipeline/scripts/run_red_blue_mimic.py`
- `/Users/hy3/Desktop/setting/xhs-pipeline/scripts/generate_xhs_variants.py`
- `/Users/hy3/Desktop/setting/xhs-pipeline/scripts/download_xhs_profile_archive.py`
- `/Users/hy3/Desktop/setting/xhs-pipeline/scripts/download_xhs_profile_full.py`

## Smoke command

```bash
bash scripts/smoke_ops.sh
```

## Output

- `state/ops_smoke_<timestamp>.log`

## Notes

- This skill does not publish or comment by default.
- It is intentionally small and atomic for Codex + Claude Code reuse.
