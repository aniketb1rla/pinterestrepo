# Design Reference Dataset

Graphic-design references (ads & social posts) collected from Pinterest and
sorted by industry, for training / prompting AI design models.

**3388 pins** · last updated 2026-11-27

## By industry
| Folder | Industry | Pins |
|---|---|---|
| `beauty-cosmetics` | Beauty & Cosmetics | 654 |
| `fintech-finance` | FinTech & Finance | 300 |
| `fashion-apparel` | Fashion & Apparel | 207 |
| `food-beverage` | Food & Beverage | 199 |
| `marketing-agency` | Marketing & Agencies | 155 |
| `travel-hospitality` | Travel & Hospitality | 152 |
| `tech-saas` | Tech, SaaS & Apps | 128 |
| `home-interiors` | Home, Interiors & Furniture | 128 |
| `jewelry-luxury` | Jewelry & Luxury | 123 |
| `health-wellness` | Health & Wellness | 123 |
| `real-estate` | Real Estate | 117 |
| `events-entertainment` | Events, Music & Entertainment | 116 |
| `construction-trades` | Construction & Home Services | 113 |
| `healthcare-medical` | Healthcare & Medical | 113 |
| `pets` | Pets | 112 |
| `automotive` | Automotive | 112 |
| `gaming-esports` | Gaming & Esports | 109 |
| `fitness-sports` | Fitness & Sports | 103 |
| `nonprofit-cause` | Non-profit & Causes | 103 |
| `legal-professional` | Legal & Professional Services | 101 |
| `education` | Education & Courses | 78 |
| `ecommerce-retail` | E-commerce & Retail | 41 |
| `uncategorized` | uncategorized | 1 |

## By format
| Format | Pins |
|---|---|
| ad-creative | 1522 |
| instagram-post | 676 |
| poster-flyer | 481 |
| story-reel | 257 |
| carousel | 151 |
| other | 124 |
| display-banner | 44 |
| email | 40 |
| landing-page | 36 |
| packaging | 31 |
| logo-branding | 26 |

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
