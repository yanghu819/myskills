# Run Log: hard-thing pixel-match

- Date: 2026-02-28
- Theme: 《创业维艰》
- Goal: style rhythm alignment with target Xiaohongshu note while keeping original subject

## What worked

- Cover structure with hero anchor improved click intent significantly.
- Short actionable lines outperformed long explanatory paragraphs.
- Evidence cards were readable only after limiting node count and enlarging text.
- Copy rhythm improved after moving from "teaching notes" to "conversion cards".

## What failed

- Kimi post-processing endpoint returned 403 for current key in this environment.
- Over-decorated layouts reduced readability and looked off-style.
- Nested small infographic blocks hurt mobile readability.

## Defaults promoted

- Keep cover hook in two short lines.
- Keep proof cards only on 2/6/7/9.
- Keep one action verb per card.
- Disable non-essential chips/strips when content density is high.

## Next run checklist

- Create 3 first-card variants before full render.
- Force CTA sentence length <= 18 Chinese chars per line.
- Run preview sheet first, then single-card QA on 1/2/9/10.
