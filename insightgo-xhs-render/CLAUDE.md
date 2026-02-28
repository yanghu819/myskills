# InsightGo XHS Renderer — Agent Instructions

## Purpose
Render minimalist essay-style Xiaohongshu carousel cards that replicate the InsightGo成长计划 visual style.

## Usage
1. Write content in markdown format (see SKILL.md for syntax)
2. Run: python3 scripts/render_insightgo_style.py input.md --output-dir output/
3. Review rendered PNGs and adjust content/spacing as needed

## Tips
- Each blank line in markdown adds ~4px gap (minimal). Content flows tightly.
- Use ==text== sparingly for emphasis (2-4 highlighted lines per page max)
- Quote blocks (>) automatically get grey left bar styling
- Use --- to force page breaks at strategic points
- Aim for ~15 pages total for engagement
- Use Chinese quotes  not ASCII quotes
- Cover works best with just brand + title (no photo needed)
