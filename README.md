# Pinterest Reference Collector

Opens a real Chrome window (Playwright) with **your saved Pinterest login**,
searches your keywords, downloads the pins, **sorts them into industry
folders**, writes a training caption for each, and pushes everything to
**github.com/aniketb1rla/pinterestrepo** as a dataset you can train or prompt AI with.

---

## 1. Open in Antigravity
1. Unzip this folder → Antigravity → **File › Open Folder** → pick `pinterest-ref-collector`.
2. Antigravity's agent reads `AGENTS.md` automatically and gets two workflows
   (`.agents/workflows/`): **collect-references** and **add-industry**.
   In the Agent panel just say: *"collect 50 references for 'fintech instagram post'"*.

## 2. One-time setup
Needs Python 3.10+, Git and Google Chrome.

| Windows | macOS / Linux |
|---|---|
| double-click `setup.bat` | `./setup.sh` |

Then open `.env` and check the settings (the defaults already point at your repo).

**GitHub access** — any one of:
- you're already logged in to GitHub in git (GitHub Desktop / `gh auth login` / Git Credential Manager), or
- paste a fine-grained token in `GITHUB_TOKEN` (repo: `pinterestrepo`, Contents: Read & write).

## 3. Log in to Pinterest once
```
python -m src.login
```
Chrome opens on Pinterest → sign in normally (email or **Continue with Google**).
The session is saved in `.auth/browser-profile/`, so every future run is already
logged in. If Pinterest ever logs you out, just run it again.

> Pinterest doesn't offer a "search pins" API for personal apps, so this uses
> your real logged-in browser session rather than an OAuth token — same result,
> and nothing to get approved.

## 4. Collect & Download

### Collect by Search Keywords
```bash
python -m src.collect "fintech instagram post" --limit 60
python -m src.collect "coffee shop poster" "burger ad" --limit 40
python -m src.collect --file keywords.txt --limit 30
python -m src.collect "roofing flyer" --industry construction-trades
```

### Download Specific Pins & Boards
Download individual pins by Pin URL, `pin.it` short link, Pin ID, or entire boards into your dataset repo or a local folder:
```bash
# Download a pin by URL or pin.it link into the dataset
python -m src.download "https://www.pinterest.com/pin/123456789/"
python -m src.download "https://pin.it/7xK9l0M"

# Download raw images directly to a local folder (with metadata .json & .txt)
python -m src.download "123456789" "987654321" --output ./downloads

# Download all pins from a Pinterest Board
python -m src.download "https://www.pinterest.com/username/boardname/" --limit 40

# Download multiple pins from a text file
python -m src.download --file pins.txt -o ./downloads

# Or pass URLs directly to src.collect
python -m src.collect "https://www.pinterest.com/pin/123456789/"
```

Use `.venv\Scripts\python` (Windows) or `.venv/bin/python` if the venv isn't activated.

| Flag | What it does |
|---|---|
| `-o`, `--output dir` | Save images & metadata directly into a local folder (e.g. `./downloads`) |
| `--also-dataset` | When using `--output`, also save into dataset repository |
| `--limit N` | pins per keyword or board (default 50) |
| `--industry slug` | force the folder instead of auto-sorting |
| `--classifier gemini` | AI-sort by looking at the image (see below) |
| `--include-videos` / `--include-promoted` | off by default |
| `--min-side 400` | skip small images |
| `--headless` | hide the browser |
| `--no-push` | save locally only |

Already-collected pins and near-duplicate images are skipped automatically,
so you can re-run the same keyword or URL list to grow the set.

## 5. Better sorting + captions with Gemini (recommended)
Get a free key at aistudio.google.com/apikey, then in `.env`:
```
CLASSIFIER=gemini
GEMINI_API_KEY=your-key
DROP_NON_DESIGN=true     # optional: skip plain photos
```
Gemini looks at each image and fills: industry, format (IG post, story,
banner, poster…), style tags, layout, typography, on-image text, CTA, and a
2–3 sentence training caption. Upgrade pins you already collected:
```
python -m src.reclassify --classifier gemini
```

## 6. Front-End UI Gallery
Browse, search, and inspect all saved design references in a responsive Pinterest-style web UI:
```
python -m src.server --open
```
Or double-click `ui.bat` on Windows.
- **Instant Search & Filters**: Search keywords, filter by 22 industries and creative formats.
- **Inspector Lightbox**: Click any pin to view high-res image, extracted 5-color palette (click to copy hex), training caption, and direct Pinterest links.
- **Offline & Zero Config**: Runs directly using Python standard library without extra dependencies.

## 7. Design Analysis & Prompt Template Generator
Deconstruct any saved reference pin into its design DNA and generate production-ready AI prompt templates:
- **Layout & Composition**: Spatial hierarchy, composition balance, aspect ratio (4:5, 9:16, 1:1), and negative space density.
- **Typography & Fonts**: Headline and body font categories, recommended Google Fonts pairings (e.g. Satoshi, Playfair Display, Syne, Inter), casing, and treatments.
- **Colors & Palette**: Extracted swatches, background and primary accents, contrast luminance, and emotional color mood.
- **Visual Aesthetic & Elements**: Design movement (e.g. Swiss Neo-Brutalist, Organic Skincare Minimalist, Glassmorphic SaaS), lighting, and decorative elements.
- **Prompt Presets**:
  - **Ad Creative Template**: Parameterized template with live interactive variable slots (`{{BRAND_NAME}}`, `{{PRODUCT_NAME}}`, `{{HEADLINE}}`, `{{CTA}}`).
  - **Midjourney v6.1**: Art direction prompt with `--ar 4:5 --style raw --v 6.1`.
  - **FLUX.1 / SDXL**: High-precision text-to-image prompt.
  - **Figma / CSS Tokens**: `:root` CSS variables and layout specifications.

### Using via Web UI
Open `ui.bat` or `python -m src.server --open`, click any pin, and press **✨ Analyze & Create Prompt Templates**. You can also browse and manage saved templates in the **📑 Prompts** library.

### Using via CLI
```bash
# Analyze pin and view all prompt templates
python -m src.prompt_template <pin_id>

# Export specific format (midjourney | flux | creative | figma | summary)
python -m src.prompt_template <pin_id> --format midjourney

# Fill in custom brand variables
python -m src.prompt_template <pin_id> --brand "Acme" --product "Glow Serum"

# Save template to library
python -m src.prompt_template <pin_id> --save

# List saved templates
python -m src.prompt_template --list
```

## 8. What lands in the repo
```
pinterestrepo/
  README.md                         auto stats table
  dataset/fintech-finance/123.jpg   image (max 1440px)
  dataset/fintech-finance/123.txt   training caption
  dataset/fintech-finance/metadata.jsonl
  index/pins.jsonl                  master database, one record per pin
  index/stats.json
  index/templates.jsonl             saved prompt templates library
  templates/<template_id>.md        human-readable markdown prompt specs
```
- **LoRA / fine-tune** (kohya, ai-toolkit, Flux/SDXL trainers): point at a
  `dataset/<industry>/` folder — image + same-name `.txt` caption pairs.
- **Prompting / RAG** (Nano Banana, GPT image, Claude): filter
  `index/pins.jsonl` by `industry`, `format`, `style_tags` and pass the
  `caption` + `layout` + image as references.

## 9. Industries
22 built in (fintech, SaaS, F&B, beauty, fashion, jewelry, real estate,
construction/roofing, healthcare, legal, non-profit, pets…). Edit
`config/categories.yaml` to add or tweak, then `python -m src.reclassify`.

## Current Dataset Statistics

**1004 pins** · last updated 2026-10-27

### By industry
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

### By format
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
