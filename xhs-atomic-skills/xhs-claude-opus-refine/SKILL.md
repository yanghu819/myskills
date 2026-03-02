---
name: xhs-claude-opus-refine
description: Refine Xiaohongshu card markdown with local Claude Opus using red/blue/layout/cover passes, then hand off to direct renderer. Use when users ask for 狠改文案、去AI味、提高点击、避免重叠和短句可读.
---

# xhs-claude-opus-refine

Use this skill to run deterministic copy refinement through local Claude CLI (Opus) before rendering.

## Inputs
- Source markdown path (10-card XHS markdown)
- Output root directory
- Pass sequence (default: red -> blue -> layout)
- Max line chars (default: 14-16)
- Claude proxy (default local 7897)

## Workflow
1. Red pass (`--pass red`): amplify hook and urgency.
2. Blue pass (`--pass blue`): improve actionability and compliance.
3. Layout pass (`--pass layout`): shorten lines and reduce overlap risk.
4. Optional cover pass (`--pass cover`) for first-card only punch.
5. Validate output:
   - frontmatter present
   - card count = 10
6. Render with `xhs-direct-render` skill.

## Primary script
- `python3 scripts/refine_markdown_with_claude.py --input <in.md> --output <out.md> --pass <red|blue|layout|cover> --model opus --effort high --max-line-chars 14`

## Quality gates
- Card1 must contain sharp pain hook.
- Card9 must be checklist (`- [ ] ...`).
- Card10 must include quote/closing CTA and no truncation.
- No forbidden absolute terms.

## Mandatory memory update
- Append each run summary to `../state/YYYY-MM-DD-<topic>.md`.
- Promote stable defaults into `../LEARNINGS.md`.
- Commit + push to `main`.
