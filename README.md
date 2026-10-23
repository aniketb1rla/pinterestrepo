# Design Reference Dataset

Graphic-design references (ads & social posts) collected from Pinterest and
sorted by industry, for training / prompting AI design models.

**807 pins** · last updated 2026-10-23

## By industry
| Folder | Industry | Pins |
|---|---|---|
| `beauty-cosmetics` | Beauty & Cosmetics | 292 |
| `food-beverage` | Food & Beverage | 90 |
| `fintech-finance` | FinTech & Finance | 80 |
| `uncategorized` | uncategorized | 60 |
| `jewelry-luxury` | Jewelry & Luxury | 41 |
| `real-estate` | Real Estate | 41 |
| `healthcare-medical` | Healthcare & Medical | 41 |
| `tech-saas` | Tech, SaaS & Apps | 40 |
| `fitness-sports` | Fitness & Sports | 40 |
| `construction-trades` | Construction & Home Services | 38 |
| `health-wellness` | Health & Wellness | 17 |
| `fashion-apparel` | Fashion & Apparel | 14 |
| `marketing-agency` | Marketing & Agencies | 5 |
| `ecommerce-retail` | E-commerce & Retail | 4 |
| `travel-hospitality` | Travel & Hospitality | 1 |
| `home-interiors` | Home, Interiors & Furniture | 1 |
| `nonprofit-cause` | Non-profit & Causes | 1 |
| `pets` | Pets | 1 |

## By format
| Format | Pins |
|---|---|
| instagram-post | 285 |
| ad-creative | 277 |
| poster-flyer | 98 |
| logo-branding | 39 |
| email | 38 |
| unknown | 31 |
| carousel | 24 |
| landing-page | 12 |
| story-reel | 2 |
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
