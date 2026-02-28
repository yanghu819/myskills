---
name: xhs-copy-redblue
description: Generate and refine high-hook Xiaohongshu conversion copy with red-team/blue-team iteration. Use when users ask for 狠改文案, 去AI味, stronger hooks, or conversion-oriented card copy.
---

# xhs-copy-redblue

Use this skill for conversion-oriented copy rewrite.

## Inputs
- Source outline or markdown (`book_outline.v1.json` or xhs md)
- Campaign mode: `conversion` or `collection`
- Optional Kimi post-process API key/base URL

## Workflow
1. Start from source content.
2. Run red-team pass (maximize hook/tension).
3. Run blue-team pass (compliance/readability/actionability).
4. Keep one main conclusion + one action sentence per card.
5. Enforce constraints:
   - no absolute claims (`100%`, `唯一`, `暴富`)
   - short lines for mobile readability
6. Save outputs:
   - final markdown for cards
   - publish copy with title variants A/B/C
7. **Mandatory memory update**:
   - append a run log under `../state/YYYY-MM-DD-<topic>.md`
   - if a new winning pattern appears, promote it into `../LEARNINGS.md`
   - commit and push to `main`

## Primary script
- `python3 scripts/run_red_blue_mimic.py ...`

## Quality gates
- Card 1: audience + pain + promised result
- Card 9: actionable checklist
- Card 10: tonight action + tomorrow review CTA
