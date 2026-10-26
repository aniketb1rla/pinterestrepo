"""Sorts pins into industry folders and writes training captions.

keywords (default, free, offline): matches config/categories.yaml.
gemini (recommended): looks at the image itself and returns industry,
format, style, layout, on-image text and a rich training caption.
Falls back to keywords automatically if Gemini fails.
"""
import json
import re
from functools import lru_cache

import yaml

from . import config


@lru_cache(maxsize=1)
def load_categories() -> dict:
    with open(config.CATEGORIES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _score_terms(terms: list[str], text: str) -> float:
    score = 0.0
    for t in terms:
        t_str = str(t).lower().strip()
        matches = len(re.findall(rf"(?<![\w-]){re.escape(t_str)}(?![\w-])", text))
        if matches:
            words = len(t_str.split())
            weight = words * 2.0 if words > 1 else 1.0
            score += matches * weight
    return score


def _keyword_scores(pin: dict, table: dict) -> dict[str, float]:
    meta = " ".join(str(pin.get(k) or "") for k in
                    ("title", "description", "alt_text", "board", "source_domain")).lower()
    query = (pin.get("query") or "").lower()
    scores = {}
    for slug, spec in table.items():
        kws = spec["keywords"] if isinstance(spec, dict) else spec
        q_score = _score_terms(kws, query)
        m_score = _score_terms(kws, meta)
        total = 10.0 * q_score + m_score
        if total > 0:
            scores[slug] = total
    return scores


def keyword_classify(pin: dict) -> dict:
    cats = load_categories()
    ind = _keyword_scores(pin, cats["industries"])
    fmt = _keyword_scores(pin, cats.get("formats", {}))
    industry = max(ind, key=ind.get) if ind else cats.get("fallback", "uncategorized")
    text_bits = [pin.get("title"), pin.get("alt_text"), pin.get("description")]
    caption = ". ".join(b.strip().rstrip(".") for b in text_bits if b and b.strip())[:600]
    return {
        "industry": industry,
        "format": max(fmt, key=fmt.get) if fmt else None,
        "is_design": None,
        "style_tags": [],
        "layout": None,
        "typography": None,
        "on_image_text": None,
        "cta": None,
        "caption": caption or f"{industry.replace('-', ' ')} design reference for '{pin.get('query')}'",
        "classified_by": "keywords",
    }


_PROMPT = """You are cataloguing graphic-design references for an AI training dataset of
ad creatives and social media posts. Look at the image and its Pinterest metadata.

Pinterest metadata:
- search query: {query}
- title: {title}
- description: {description}
- alt text: {alt}

Pick ONE industry slug from this list (use "{fallback}" if none fits):
{industries}

Return ONLY JSON with exactly these keys:
{{
  "industry": "<slug>",
  "is_design": <true if it is a designed graphic/ad/social post/poster with layout or typography, false if it is a plain photo>,
  "format": "<one of: {formats}, other>",
  "style_tags": ["3-8 short style words, e.g. minimal, bold-typography, 3d-render, gradient, flat-illustration, luxury, retro"],
  "layout": "<one sentence: composition and hierarchy, e.g. 'centered product hero, headline top, CTA button bottom-right'>",
  "typography": "<one sentence on type: families/weights/case/treatment>",
  "on_image_text": "<all readable text on the image, verbatim, or empty string>",
  "cta": "<call-to-action text if any, else empty string>",
  "caption": "<2-3 sentence training caption describing the design so a model could recreate its style: subject, layout, colours, typography, mood, format>"
}}"""


def _gemini_client():
    from google import genai  # imported lazily so keyword mode needs no extra package
    return genai.Client(api_key=config.GEMINI_API_KEY)


def gemini_classify(pin: dict, image_bytes: bytes) -> dict:
    from google.genai import types

    cats = load_categories()
    industries = "\n".join(f"- {k}: {v['label']}" for k, v in cats["industries"].items())
    prompt = _PROMPT.format(
        query=pin.get("query"), title=pin.get("title") or "-", description=(pin.get("description") or "-")[:500],
        alt=pin.get("alt_text") or "-", industries=industries,
        fallback=cats.get("fallback", "uncategorized"), formats=", ".join(cats.get("formats", {}).keys()),
    )
    resp = _gemini_client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"), prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
    )
    data = json.loads(resp.text)
    if data.get("industry") not in cats["industries"]:
        data["industry"] = cats.get("fallback", "uncategorized")
    data["classified_by"] = f"gemini:{config.GEMINI_MODEL}"
    return data


def classify(pin: dict, image_bytes: bytes, force_industry: str | None = None,
             mode: str | None = None) -> dict:
    mode = (mode or config.CLASSIFIER).lower()
    result = None
    if mode == "gemini":
        if not config.GEMINI_API_KEY:
            print("  [classifier] GEMINI_API_KEY missing in .env — using keywords.")
        else:
            try:
                result = gemini_classify(pin, image_bytes)
            except Exception as exc:
                print(f"  [classifier] Gemini failed for {pin['pin_id']} ({exc}); using keywords.")
    if result is None:
        result = keyword_classify(pin)
    if force_industry:
        result["industry"] = force_industry
    return result
