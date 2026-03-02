# 2026-03-02 unified musk publish

## What changed

- Added unified XHS entrypoint folder: `xiaohongshu-unified/`.
- Added reusable script:
  - `scripts/build_musk_bio_outline.py`
  - `scripts/run_book_to_xhs_publish.sh`
- Unified flow now supports:
  - `book_outline.v1.json` generation for new book themes
  - smoke render (10 cards)
  - publish dry-run
  - real publish with cookie fallback from local Chrome login state

## Key lessons

1. `render_manifest.v1.json` schema mismatch:
   - existing publisher expected `cards`
   - renderer emits `images`
   - fixed by resolving absolute image list before publishing.

2. macOS default bash (`3.2`) lacks `mapfile`:
   - replaced with `while read` array assembly for portability.

3. publish dry-run still validates cookie:
   - added placeholder cookie injection only for dry-run when no `XHS_COOKIE`.

4. real publish without env cookie:
   - fallback to `browser_cookie3.chrome(domain_name="xiaohongshu.com")`
   - avoids storing cookie in repo while supporting logged-in local browser.
