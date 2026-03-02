# 2026-03-02 HardThing v18c Private Publish

## Publish target
- Theme: 《创业维艰》10张决策卡
- Render set: `hard-thing-claude-opus/20260302T062613Z/rendered_v18c`
- Mode: private note (仅自己可见)

## Result
- note_id: `69a564ed000000002603d4cd`
- url: `https://www.xiaohongshu.com/explore/69a564ed000000002603d4cd`
- publish timestamp (local run): 2026-03-02

## Command pattern (stable)
1. build cookie from local browser (browser_cookie3)
2. `publish_xhs.py --manifest <manifest.json> --title <<=20 chars> --desc <copy> --private --cookie <cookie>`
3. parse note_id/url and persist `publish_result*.json`

## Notes
- Dry-run succeeded before real publish.
- Using manifest-based publish avoids image list path mismatch.
