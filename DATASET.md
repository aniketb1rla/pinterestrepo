# Design Reference Dataset

Graphic-design references (ads & social posts) collected from Pinterest and
sorted by industry, for training / prompting AI design models.

**1964 pins** · last updated 2026-11-26

## By industry
| Folder | Industry | Pins |
|---|---|---|
| `beauty-cosmetics` | Beauty & Cosmetics | 542 |
| `fintech-finance` | FinTech & Finance | 234 |
| `fashion-apparel` | Fashion & Apparel | 120 |
| `food-beverage` | Food & Beverage | 115 |
| `travel-hospitality` | Travel & Hospitality | 109 |
| `marketing-agency` | Marketing & Agencies | 82 |
| `jewelry-luxury` | Jewelry & Luxury | 56 |
| `home-interiors` | Home, Interiors & Furniture | 54 |
| `fitness-sports` | Fitness & Sports | 53 |
| `healthcare-medical` | Healthcare & Medical | 52 |
| `education` | Education & Courses | 52 |
| `pets` | Pets | 51 |
| `automotive` | Automotive | 51 |
| `tech-saas` | Tech, SaaS & Apps | 49 |
| `nonprofit-cause` | Non-profit & Causes | 49 |
| `real-estate` | Real Estate | 47 |
| `construction-trades` | Construction & Home Services | 47 |
| `legal-professional` | Legal & Professional Services | 46 |
| `gaming-esports` | Gaming & Esports | 45 |
| `health-wellness` | Health & Wellness | 41 |
| `ecommerce-retail` | E-commerce & Retail | 37 |
| `events-entertainment` | Events, Music & Entertainment | 32 |

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
