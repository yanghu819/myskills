---
name: xhs-profile-archive
description: Archive a Xiaohongshu user profile into a local folder, including notes, note titles/bodies, images, and comments. Use when users ask to download/backup 全部笔记内容 from a profile URL.
---

# xhs-profile-archive

Use this skill when the user wants full-profile scraping/backup for Xiaohongshu.

## Inputs
- Profile URL (must contain `/user/profile/<user_id>`)
- Output root path (optional, default in script)

## Workflow
1. Ensure browser login cookies exist for xiaohongshu.com (local Chrome cookie store).
2. Run script:
   - `python3 scripts/download_xhs_profile_full.py --profile-url "<URL>" --output-root "<DIR>"`
3. Validate output:
   - `summary.json` exists
   - `notes_index.json` exists
   - `notes/*/content.md`, `notes/*/comments.json`, `notes/*/images/` exist
4. Return absolute archive path and counts.

## Output contract
- `summary.json`: note/image/comment totals
- `notes_index.json`: per-note index
- `notes/<idx_noteid>/content.md`
- `notes/<idx_noteid>/note_detail.json`
- `notes/<idx_noteid>/comments.json`
- `notes/<idx_noteid>/images/*`

## Safety
- Use logged-in session only; do not bypass auth.
- If comments are partially missing, report it explicitly.
