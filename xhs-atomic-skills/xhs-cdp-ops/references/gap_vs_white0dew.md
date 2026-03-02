# Gap Snapshot: Our Pipeline vs `white0dew/XiaohongshuSkills`

## Already aligned

- Deterministic CLI scripts for rendering and archive.
- Profile archive with notes + comments + images.
- Multi-step pipeline orchestration and smoke tests.
- Private publish path in existing vendor scripts.

## Newly aligned in this iteration

- Single-instance runtime locking for high-frequency scripts.
- Explicit lock-conflict exit handling.
- Login TTL cache and lightweight session check fallback.
- Structured `*_RESULT` output and optional CSV export.

## Not yet aligned (next iteration candidates)

1. Unified CDP ops command set
- `check-login`, `search-feeds`, `get-feed-detail`, `post-comment-to-feed`, `content-data`.

2. Unified CDP ops command set
- `check-login`, `search-feeds`, `get-feed-detail`, `post-comment-to-feed`, `content-data`.

3. Remote CDP host/port mode
- Useful when browser and control plane are separated.

## Recommendation

- Keep our rendering/content pipeline as-is.
- Add a separate `xhs-cdp-ops` track for interaction/ops automation so concerns remain decoupled.
