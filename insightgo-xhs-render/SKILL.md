# insightgo-xhs-render

Render InsightGo-style Xiaohongshu (XHS) essay cards from markdown into 1080x1440 PNG images.

## When to Use
- Creating long-form essay-style XHS carousel posts
- Replicating the InsightGo成长计划 visual style (minimalist, off-white bg, yellow highlights)
- Converting book notes / deep-thinking content into XHS image posts

## Inputs
- A markdown file using this format:
  - `@@brand:Name` — brand text (top-left)
  - `@@tagline:Text` — tagline (bottom of cover)
  - `@@photo:path` — optional cover photo
  - `# Title` — cover title (first H1 only)
  - `## Heading` — section headings (bold, large)
  - `==text==` — yellow highlighted text
  - `> quote` — quote blocks with grey left bar
  - `- item` — bullet points with ● symbol
  - `---` — page break / chunk separator
  - Blank lines between sentences for line-by-line flow

## Command
```bash
python3 scripts/render_insightgo_style.py input.md --output-dir output/
```

## Dependencies
- Python 3.8+
- Pillow (PIL)
- macOS system CJK fonts (STHeiti, Hiragino Sans GB) or Noto CJK fonts

## Key Style Parameters (LayoutConfig)
- Background: #FAFAF5 (off-white)
- Body: 40px, line-height 78px
- Headings: 62px bold, black
- Highlights: #FFF3CC (light yellow)
- Quote bar: 4px grey #CCCCCC
- Margins: 60px L/R, 50px top, 60px bottom
- ~16 lines per page for optimal density
