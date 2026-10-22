# Design Reference Dataset

Graphic-design references (ads & social posts) collected from Pinterest and
sorted by industry, for training / prompting AI design models.

**476 pins** · last updated 2026-10-22

## By industry
| Folder | Industry | Pins |
|---|---|---|
| `fintech-finance` | FinTech & Finance | 79 |
| `food-beverage` | Food & Beverage | 78 |
| `beauty-cosmetics` | Beauty & Cosmetics | 50 |
| `tech-saas` | Tech, SaaS & Apps | 45 |
| `jewelry-luxury` | Jewelry & Luxury | 40 |
| `real-estate` | Real Estate | 40 |
| `healthcare-medical` | Healthcare & Medical | 40 |
| `fitness-sports` | Fitness & Sports | 40 |
| `construction-trades` | Construction & Home Services | 38 |
| `uncategorized` | uncategorized | 11 |
| `ecommerce-retail` | E-commerce & Retail | 8 |
| `marketing-agency` | Marketing & Agencies | 2 |
| `travel-hospitality` | Travel & Hospitality | 2 |
| `health-wellness` | Health & Wellness | 2 |
| `fashion-apparel` | Fashion & Apparel | 1 |

## By format
| Format | Pins |
|---|---|
| instagram-post | 249 |
| poster-flyer | 88 |
| unknown | 78 |
| email | 38 |
| landing-page | 11 |
| logo-branding | 8 |
| story-reel | 2 |
| carousel | 1 |
| packaging | 1 |

## Layout
```
dataset/<industry>/<pin_id>.jpg       image (max 1440px)
dataset/<industry>/<pin_id>.txt       training caption
dataset/<industry>/metadata.jsonl     per-industry records
index/pins.jsonl                      master database (one JSON per line)
index/stats.json                      counts
```

Each record holds: pin_id, pin_url, image_url, title, description, alt_text,
query, industry, format, is_design, style_tags, layout, typography,
on_image_text, cta, caption, palette, aspect_ratio, source_domain, pinner,
board, dhash, collected_at.

## Use for training
- **LoRA / fine-tune (kohya, ai-toolkit, diffusers):** point at
  `dataset/<industry>/` — images and same-name `.txt` captions are paired.
- **Few-shot prompting / RAG:** load `index/pins.jsonl`, filter by
  `industry`, `format`, `style_tags`, feed `caption` + `layout` + image.

> Images belong to their original creators. Kept as private reference
> material; check licensing before any commercial model training.
