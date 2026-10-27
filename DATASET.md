# Design Reference Dataset

Graphic-design references (ads & social posts) collected from Pinterest and
sorted by industry, for training / prompting AI design models.

**1004 pins** · last updated 2026-10-27

## By industry
| Folder | Industry | Pins |
|---|---|---|
| `beauty-cosmetics` | Beauty & Cosmetics | 303 |
| `fintech-finance` | FinTech & Finance | 221 |
| `food-beverage` | Food & Beverage | 93 |
| `uncategorized` | uncategorized | 69 |
| `jewelry-luxury` | Jewelry & Luxury | 42 |
| `real-estate` | Real Estate | 41 |
| `healthcare-medical` | Healthcare & Medical | 41 |
| `tech-saas` | Tech, SaaS & Apps | 40 |
| `fitness-sports` | Fitness & Sports | 40 |
| `construction-trades` | Construction & Home Services | 38 |
| `ecommerce-retail` | E-commerce & Retail | 32 |
| `health-wellness` | Health & Wellness | 21 |
| `fashion-apparel` | Fashion & Apparel | 14 |
| `marketing-agency` | Marketing & Agencies | 5 |
| `travel-hospitality` | Travel & Hospitality | 1 |
| `home-interiors` | Home, Interiors & Furniture | 1 |
| `nonprofit-cause` | Non-profit & Causes | 1 |
| `pets` | Pets | 1 |

## By format
| Format | Pins |
|---|---|
| ad-creative | 320 |
| instagram-post | 286 |
| unknown | 123 |
| poster-flyer | 106 |
| logo-branding | 63 |
| landing-page | 40 |
| email | 38 |
| carousel | 25 |
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
