---
description: Add a new industry category and re-sort existing pins into it
---

1. Ask the user for the industry name and a few example keywords.
2. Add an entry to `config/categories.yaml` under `industries:` with a lowercase-hyphen slug, a `label`, and a `keywords` list (10–20 terms, lowercase).
3. Run `python -m src.reclassify --only-uncategorized` (or `--classifier gemini` for a full re-sort if GEMINI_API_KEY is set).
4. Show the user the new counts from `pinterestrepo/index/stats.json`.
