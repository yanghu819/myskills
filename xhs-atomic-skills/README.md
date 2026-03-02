# xhs-atomic-skills

Atomic skills for Xiaohongshu workflows: archive, copy iteration, direct rendering, variant preview, and reusable book-swap smoke tests.

## Skills

- `xhs-profile-archive`: archive a Xiaohongshu profile locally (content + comments + media index)
- `xhs-copy-redblue`: conversion-oriented copy rewrite with red/blue iteration
- `xhs-direct-render`: deterministic large-type direct rendering
- `xhs-variants-preview`: multi-version generation and preview sheets
- `xhs-book-reuse-smoke`: swap-in new `book_outline.v1.json` and run full smoke (assets -> md -> 10 cards -> manifest verification)
  - includes `zero_to_one` and `hard_thing_persona` presets for fast reuse

## Immediate Backup Rule

When finishing any meaningful iteration:

1. Update `state/YYYY-MM-DD-<topic>.md` with wins/failures/defaults.
2. Update `LEARNINGS.md` if a default changed.
3. Commit + push to `main`.

This repository is the durable memory for Codex + Claude Code reuse.
