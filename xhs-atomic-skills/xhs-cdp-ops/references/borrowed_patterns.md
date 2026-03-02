# Borrowed Patterns From `white0dew/XiaohongshuSkills`

## Directly adopted

1. Single-instance runtime lock
- Prevents parallel runs from corrupting output folders or browser state.
- Implemented via `xhs-pipeline/scripts/run_lock.py`.

2. Lock-aware script entrypoint
- Script exits early with explicit conflict message and non-zero status when another run is active.
- Added to:
  - `run_red_blue_mimic.py`
  - `generate_xhs_variants.py`
  - `download_xhs_profile_archive.py`
  - `download_xhs_profile_full.py`

## High-value patterns to adopt next

1. Login status cache with TTL
- Avoids repeated expensive login checks during batch ops.

2. Timing jitter for anti-rigid automation behavior
- Adds bounded random delays to avoid deterministic action rhythm.

3. Unified command taxonomy
- `check-login`, `search-feeds`, `get-feed-detail`, `post-comment-to-feed`, `content-data`.

4. Structured result envelope
- Standardized JSON output blocks (`*_RESULT`) for downstream scripts.

5. CSV export path for analytics
- Content metrics easy to consume in dashboards.

## Integration principle

- Borrow architecture and workflow patterns.
- Do not copy third-party brand claims or account-specific strategies.
