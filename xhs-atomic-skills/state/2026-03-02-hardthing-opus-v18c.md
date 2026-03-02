# 2026-03-02 HardThing Opus v18c

## What changed
- Added structured copy markers to boost component rendering:
  - `!!!` emphasis lines
  - `@@proof:` evidence bar
  - `@@benefit:` chip panel
  - `- [ ]` checklist for card 9
- Switched bullet symbol in direct renderer from `•` to `·` to avoid glyph fallback square boxes.
- Shortened quote card text to avoid truncation under high font scale.

## Winning defaults (current)
- Renderer: `editorial_unified_v1`
- Scales: `--font-scale 1.20 --heading-scale 1.34 --emphasis-scale 1.38`
- Wrap controls: `--max-chars-per-line 12 --max-lines-per-block 2`

## Artifacts
- Markdown: `xhs_post.v18.structured.md`
- Render: `rendered_v18c/01-card.png ... 10-card.png`

## Notes
- This version improved hook density and preserved readability without overlap on key cards.
