# Design Reference Dataset

Graphic-design references (ads & social posts) collected from Pinterest and
sorted by industry, for training / prompting AI design models.

**3351 pins** · last updated 2026-11-26

## By industry
| Folder | Industry | Pins |
|---|---|---|
| `beauty-cosmetics` | Beauty & Cosmetics | 605 |
| `fintech-finance` | FinTech & Finance | 291 |
| `fashion-apparel` | Fashion & Apparel | 181 |
| `food-beverage` | Food & Beverage | 180 |
| `travel-hospitality` | Travel & Hospitality | 173 |
| `marketing-agency` | Marketing & Agencies | 146 |
| `home-interiors` | Home, Interiors & Furniture | 119 |
| `jewelry-luxury` | Jewelry & Luxury | 118 |
| `healthcare-medical` | Healthcare & Medical | 117 |
| `fitness-sports` | Fitness & Sports | 117 |
| `pets` | Pets | 116 |
| `automotive` | Automotive | 116 |
| `education` | Education & Courses | 115 |
| `tech-saas` | Tech, SaaS & Apps | 112 |
| `construction-trades` | Construction & Home Services | 112 |
| `real-estate` | Real Estate | 111 |
| `gaming-esports` | Gaming & Esports | 110 |
| `legal-professional` | Legal & Professional Services | 109 |
| `nonprofit-cause` | Non-profit & Causes | 108 |
| `health-wellness` | Health & Wellness | 104 |
| `events-entertainment` | Events, Music & Entertainment | 97 |
| `ecommerce-retail` | E-commerce & Retail | 94 |

## By format
| Format | Pins |
|---|---|
| ad-creative | 1573 |
| poster-flyer | 632 |
| instagram-post | 443 |
| unknown | 407 |
| logo-branding | 74 |
| landing-page | 69 |
| display-banner | 66 |
| email | 39 |
| carousel | 28 |
| story-reel | 18 |
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
