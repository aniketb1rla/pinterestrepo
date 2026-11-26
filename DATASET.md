# Design Reference Dataset

Graphic-design references (ads & social posts) collected from Pinterest and
sorted by industry, for training / prompting AI design models.

**1964 pins** · last updated 2026-11-26

## By industry
| Folder | Industry | Pins |
|---|---|---|
| `beauty-cosmetics` | Beauty & Cosmetics | 489 |
| `fintech-finance` | FinTech & Finance | 233 |
| `uncategorized` | uncategorized | 142 |
| `travel-hospitality` | Travel & Hospitality | 112 |
| `food-beverage` | Food & Beverage | 106 |
| `fashion-apparel` | Fashion & Apparel | 70 |
| `marketing-agency` | Marketing & Agencies | 63 |
| `jewelry-luxury` | Jewelry & Luxury | 53 |
| `fitness-sports` | Fitness & Sports | 52 |
| `home-interiors` | Home, Interiors & Furniture | 52 |
| `education` | Education & Courses | 52 |
| `healthcare-medical` | Healthcare & Medical | 51 |
| `pets` | Pets | 51 |
| `real-estate` | Real Estate | 50 |
| `nonprofit-cause` | Non-profit & Causes | 49 |
| `automotive` | Automotive | 49 |
| `gaming-esports` | Gaming & Esports | 48 |
| `construction-trades` | Construction & Home Services | 47 |
| `legal-professional` | Legal & Professional Services | 47 |
| `tech-saas` | Tech, SaaS & Apps | 45 |
| `ecommerce-retail` | E-commerce & Retail | 40 |
| `events-entertainment` | Events, Music & Entertainment | 33 |
| `health-wellness` | Health & Wellness | 30 |

## By format
| Format | Pins |
|---|---|
| ad-creative | 860 |
| unknown | 370 |
| instagram-post | 348 |
| poster-flyer | 189 |
| logo-branding | 68 |
| landing-page | 46 |
| email | 38 |
| carousel | 28 |
| story-reel | 12 |
| display-banner | 3 |
| packaging | 2 |

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
