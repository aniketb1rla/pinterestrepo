# Creative Builder Kit (3,369 Analyzed Design Creatives)

This folder is a self-contained handoff package for improving the **Creative Builder**—combining structured Gemini Vision (`gemini-3.8-flash`) analysis of **3,369 real-world ad creatives, social posts, posters, and carousels** across **22 industries** with an editorial, anti-AI-slop prompt & design guide.

## What's Inside

| File / Folder | Description |
| --- | --- |
| `dataset/` | All **3,370** creative images (`.jpg`), per-pin captions (`.txt`), and `metadata.jsonl` organized into industry folders (`image_path` resolves relative to this folder). |
| `vision_analysis.jsonl` | **3,369** records in JSON Lines format (best for scripts, embeddings/RAG, and prompt pipelines). |
| `vision_analysis.csv` | Same **3,369** records in UTF-8 CSV (best for Excel, Google Sheets, and quick filtering). |
| `CREATIVE_PROMPT_AGENT_GUIDE.md` | System prompt & art-direction ruleset (anti-AI-slop guardrails, conceptualisation hooks, typography & lighting rules) distilled from the corpus. |
| `stats.json` | Aggregate counts by industry, format, and search query. |
| `categories.yaml` | Industry taxonomy (`22` slugs + labels) and creative format tags. |

## Record Schema (`vision_analysis.jsonl` / `.csv`)
- `pin_id` — Unique Pinterest creative ID
- `industry` — Industry slug (e.g. `fintech-finance`, `beauty-cosmetics`, `tech-saas`)
- `is_design` — `true` for designed graphics/ads/posters (`3,178`), `false` for plain photos (`191`)
- `format` — `ad-creative`, `instagram-post`, `poster-flyer`, `story-reel`, `carousel`, `display-banner`, `email`, `landing-page`, `packaging`, `logo-branding`, `other`
- `style_tags` — Visual aesthetic tags (e.g. `minimal`, `dark-mode`, `editorial`, `3d-render`, `bold-typography`)
- `layout` — Composition, grid, and visual hierarchy
- `typography` — Font families, weights, tracking, and styling treatment
- `on_image_text` — Verbatim text extracted from the creative
- `cta` — Call-to-action text (if present)
- `caption` — 2–3 sentence design-recreation caption
- `image_path` — Relative path to the `.jpg` in the main dataset repo
- `pin_url` — Original Pinterest reference URL
- `classified_by` — `gemini:gemini-3.8-flash`

## Quick Ways to Use This in the Creative Builder
1. **Prompt Engine**: Drop `CREATIVE_PROMPT_AGENT_GUIDE.md` into the system prompt of your creative-prompt LLM so it stops generating generic AI tropes and enforces negative space, 2–3 color discipline, and industry-matched typography.
2. **Reference Retrieval (RAG)**: Index `vision_analysis.jsonl` by `industry`, `format`, and `style_tags` (`is_design == true`) to retrieve proven `layout` + `typography` + `caption` patterns as few-shot context before generating new creatives.
3. **CTA & Copy Guardrails**: Filter `on_image_text` and `cta` by `industry` to match real-world headline lengths (2–5 words) and low-friction CTAs (`Shop Now`, `Book Now`, `Learn More`).
