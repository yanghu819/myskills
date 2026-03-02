# Gap Snapshot: Our Pipeline vs `white0dew/XiaohongshuSkills`

## Already aligned

- Deterministic CLI scripts for rendering and archive.
- Profile archive with notes + comments + images.
- Multi-step pipeline orchestration and smoke tests.
- Private publish path in existing vendor scripts.

## Newly aligned in this iteration

- Single-instance runtime locking for high-frequency scripts.
- Explicit lock-conflict exit handling.

## Not yet aligned (next iteration candidates)

1. Unified CDP ops command set
- `check-login`, `search-feeds`, `get-feed-detail`, `post-comment-to-feed`, `content-data`.

2. Login cache TTL
- Skip redundant login checks during repeated runs.

3. Structured ops result envelopes
- Stable JSON schema for downstream automation.

4. CSV-first metrics export
- Unified analytics ingestion from content data APIs.

5. Remote CDP host/port mode
- Useful when browser and control plane are separated.

## Recommendation

- Keep our rendering/content pipeline as-is.
- Add a separate `xhs-cdp-ops` track for interaction/ops automation so concerns remain decoupled.
