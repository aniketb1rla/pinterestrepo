# Design Reference Dataset

Graphic-design references (ads & social posts) collected from Pinterest and
sorted by industry, for training / prompting AI design models.

**1687 pins** · last updated 2026-11-25

## By industry
| Folder | Industry | Pins |
|---|---|---|
| `beauty-cosmetics` | Beauty & Cosmetics | 469 |
| `fintech-finance` | FinTech & Finance | 222 |
| `uncategorized` | uncategorized | 142 |
| `travel-hospitality` | Travel & Hospitality | 102 |
| `food-beverage` | Food & Beverage | 94 |
| `fashion-apparel` | Fashion & Apparel | 60 |
| `marketing-agency` | Marketing & Agencies | 54 |
| `jewelry-luxury` | Jewelry & Luxury | 43 |
| `healthcare-medical` | Healthcare & Medical | 42 |
| `real-estate` | Real Estate | 41 |
| `fitness-sports` | Fitness & Sports | 41 |
| `tech-saas` | Tech, SaaS & Apps | 40 |
| `home-interiors` | Home, Interiors & Furniture | 40 |
| `gaming-esports` | Gaming & Esports | 40 |
| `automotive` | Automotive | 39 |
| `construction-trades` | Construction & Home Services | 38 |
| `legal-professional` | Legal & Professional Services | 38 |
| `ecommerce-retail` | E-commerce & Retail | 33 |
| `health-wellness` | Health & Wellness | 24 |
| `events-entertainment` | Events, Music & Entertainment | 22 |
| `nonprofit-cause` | Non-profit & Causes | 21 |
| `pets` | Pets | 21 |
| `education` | Education & Courses | 21 |

## By format
| Format | Pins |
|---|---|
| ad-creative | 751 |
| unknown | 339 |
| instagram-post | 288 |
| poster-flyer | 118 |
| logo-branding | 67 |
| landing-page | 43 |
| email | 38 |
| carousel | 28 |
| story-reel | 12 |
| packaging | 2 |
| display-banner | 1 |

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
