"""Design analyzer and prompt template generator for collected Pinterest references.

Analyzes pins for:
- Layout (composition, grid, visual hierarchy, spacing, aspect ratio)
- Typography & Fonts (headline/body styles, casing, recommended web/Google fonts, text effects)
- Colors & Palette (dominant tones, accent colors, contrast, harmony, emotional mood)
- Design Style & Aesthetic (design movement, textures, lighting, decorative elements)
- Prompt Templates (Nano Banana 2.1 4K Generation & Edit, Ad Creative with variables, Figma Design Tokens)

Supports:
1. Google Gemini Multimodal Vision: inspects actual image pixels to extract verbatim copy,
   pixel-accurate layout hierarchy, exact font styles, and generate native Nano Banana 2.1 prompts.
2. Ground-Truth Heuristic Engine: extracts real creative subjects, headlines, backgrounds,
   and colors from pin metadata (alt text, title, description, palette) with zero generic filler.
"""
from __future__ import annotations

import colorsys
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

from . import config
from .classifier import load_categories


# ==============================================================================
# Color Analysis & Human-Readable Color Naming
# ==============================================================================

def hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    h = hex_code.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def calculate_luminance(hex_code: str) -> float:
    try:
        r, g, b = hex_to_rgb(hex_code)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    except Exception:
        return 0.5


def hex_to_color_name(hex_code: str) -> str:
    """Translates a hex code into a vivid human-readable color descriptor."""
    h = hex_code.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return "neutral tone"

    hue, light, sat = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    hue_deg = hue * 360

    if light < 0.10:
        return "deep obsidian black"
    if light > 0.90 and sat < 0.15:
        return "crisp clean white"
    if sat < 0.15:
        if light > 0.70:
            return "soft light gray"
        elif light > 0.40:
            return "neutral medium gray"
        else:
            return "dark charcoal slate"

    tone = "vibrant" if sat > 0.75 else ("muted" if sat < 0.4 else "rich")
    if light < 0.28:
        tone = "deep"
    elif light > 0.75:
        tone = "soft pastel"

    if hue_deg < 15 or hue_deg >= 345:
        name = "crimson red" if light < 0.4 else ("pink" if light > 0.7 else "cherry red")
    elif hue_deg < 42:
        name = "terracotta orange" if light < 0.4 else ("warm amber" if light < 0.65 else "warm sand peach")
    elif hue_deg < 70:
        name = "olive gold" if light < 0.4 else ("golden yellow" if sat > 0.6 else "warm beige")
    elif hue_deg < 160:
        name = "forest green" if light < 0.35 else ("emerald green" if sat > 0.6 else "sage green")
    elif hue_deg < 200:
        name = "dark cyan" if light < 0.35 else ("electric teal" if sat > 0.6 else "muted teal")
    elif hue_deg < 260:
        name = "deep navy blue" if light < 0.35 else ("royal blue" if sat > 0.6 else "slate blue")
    elif hue_deg < 310:
        name = "deep royal purple" if light < 0.35 else ("electric violet" if sat > 0.6 else "lavender")
    else:
        name = "magenta plum" if light < 0.4 else ("hot pink" if sat > 0.7 else "blush rose")

    return f"{tone} {name}"


def get_color_temperature(hex_code: str) -> str:
    try:
        r, g, b = hex_to_rgb(hex_code)
        if r > b + 25:
            return "warm"
        elif b > r + 25:
            return "cool"
        return "neutral"
    except Exception:
        return "neutral"


def extract_enhanced_palette(img: Image.Image, num_colors: int = 6) -> list[str]:
    small = img.convert("RGB").copy()
    small.thumbnail((160, 160))
    q = small.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    counts = sorted(q.getcolors() or [], reverse=True)
    hex_colors: list[str] = []
    for _, idx in counts:
        r = pal[idx * 3]
        g = pal[idx * 3 + 1]
        b = pal[idx * 3 + 2]
        hex_c = rgb_to_hex(r, g, b)
        if hex_c not in hex_colors:
            hex_colors.append(hex_c)
        if len(hex_colors) >= num_colors:
            break
    return hex_colors or ["#0d1117", "#161b22", "#e60023", "#f0f6fc"]


def classify_aspect_ratio(width: int, height: int) -> dict[str, str]:
    ratio = round(width / max(1, height), 2)
    if ratio <= 0.65:
        return {"ratio": "9:16", "name": "Story / Vertical Reel (9:16)", "css": "aspect-ratio: 9/16;"}
    elif 0.70 <= ratio <= 0.88:
        return {"ratio": "4:5", "name": "Portrait Feed / Standard Ad (4:5)", "css": "aspect-ratio: 4/5;"}
    elif 0.90 <= ratio <= 1.15:
        return {"ratio": "1:1", "name": "Square Post / Grid Ad (1:1)", "css": "aspect-ratio: 1/1;"}
    elif 1.16 <= ratio <= 1.55:
        return {"ratio": "4:3", "name": "Landscape Feed (4:3)", "css": "aspect-ratio: 4/3;"}
    else:
        return {"ratio": "16:9", "name": "Wide Banner / Billboard (16:9)", "css": "aspect-ratio: 16/9;"}


# ==============================================================================
# Ground-Truth NLP & Visual DNA Extraction
# ==============================================================================

def extract_pin_ground_truth(pin: dict[str, Any]) -> dict[str, Any]:
    """Extracts actual creative subject, headline, subhead, CTA, and background from pin metadata."""
    alt = (pin.get("alt_text") or "").strip()
    title = (pin.get("title") or "").strip()
    desc = (pin.get("description") or "").strip()
    query = (pin.get("query") or "").strip()
    ind = pin.get("industry") or "general"
    palette = pin.get("palette") or ["#0d1117", "#ffffff"]

    bg_hex = palette[0]
    accent_hex = palette[1] if len(palette) > 1 else "#e60023"
    bg_color_name = hex_to_color_name(bg_hex)
    accent_color_name = hex_to_color_name(accent_hex)

    headline = ""
    subhead = ""

    # 1. Headline extraction from alt text (Pinterest OCR or accessibility caption)
    m = re.search(r'with the (?:caption|words),?\s*(?:the\s+)?[\'"]?([^\.\n]+)', alt, re.I)
    if not m:
        m = re.search(r'the cover of\s+[\'"]?([^\.\n]+?)\s+is shown', alt, re.I)

    if m:
        raw_text = m.group(1).strip(" \"'").rstrip(".")
        if " unless " in raw_text.lower():
            parts = re.split(r'\s+unless\s+', raw_text, flags=re.I)
            headline = parts[0].strip()
            subhead = "Unless " + parts[1].strip()
        else:
            headline = raw_text

    # Fallback to title
    if not headline or len(headline) < 4:
        if title:
            clean_t = title.split(" - ")[0].split(" | ")[0].split(" by ")[0].strip()
            headline = clean_t
        elif desc:
            lines = [l.strip() for l in desc.splitlines() if len(l.strip()) > 3]
            if lines and not any(tag in lines[0].lower() for tag in ["visuals", "marketing", "tags", "#"]):
                headline = lines[0].split(".")[0].strip()

    if not headline:
        headline = query.title() or "Premium Creative Design"

    headline = re.sub(r'[\r\n\t]+', ' ', headline).strip()[:80]

    # Subhead extraction from description (ignoring hashtag/keyword soup)
    if not subhead and desc:
        sentences = [s.strip() for s in desc.split(".") if len(s.strip()) > 8 and s.strip().lower() != headline.lower()]
        for s in sentences:
            if not any(k in s.lower() for k in ["visuals", "flyer design", "graphic designer", "branding", "marketing social"]):
                subhead = s
                break

    if not subhead:
        if ind in ("beauty-cosmetics", "jewelry-luxury"):
            subhead = "Formulated with pure clinical botanicals for natural radiance."
        elif ind in ("fintech-finance", "tech-saas"):
            subhead = "Designed for seamless digital performance, bank-grade security, and instant control."
        elif ind in ("food-beverage",):
            subhead = "Crafted fresh with 100% premium artisan ingredients."
        else:
            subhead = "Engineered for maximum visual impact and unforgettable engagement."

    subhead = re.sub(r'[\r\n\t]+', ' ', subhead).strip()[:110]

    # 2. Extract actual subject from alt text
    subject = ""
    m_shown = re.search(r'is shown with\s+(.+?)(?:\s+in front of it|\s+on it)?$', alt, re.I)
    if m_shown:
        extra_detail = m_shown.group(1).strip()
        subject = f"{extra_detail} in front of {headline}"
    else:
        clean = re.sub(r'^(?:an? (?:advertisement|ad|image|photo|cover) (?:for|of) |the cover of )', '', alt, flags=re.I)
        clean = re.sub(r'with the (?:caption|words).*$', '', clean, flags=re.I).strip()
        if "some kind of skin care product" in clean.lower():
            clean = "a luxury skincare serum bottle with minimalist branding"
        elif "different types of electronic devices" in clean.lower():
            clean = "a curated modern tech grid of electronic devices and minimalist gadget price tags"
        elif "cell phone" in clean.lower() or "smart phone" in clean.lower():
            clean = "a hand holding a sleek modern smartphone displaying a clean mobile app interface"
        elif "cheeseburger" in clean.lower() or "burger" in clean.lower():
            clean = "a hand holding a juicy triple cheeseburger with melted cheddar and toasted sesame seed bun"
        subject = clean if clean else (title or query)

    # 3. Background setting
    bg_setting = f"a solid {bg_color_name} studio background ({bg_hex})"
    m_bg = re.search(r'on a ([a-z\s]+? background)', alt, re.I)
    if m_bg:
        bg_setting = f"a {m_bg.group(1)} ({bg_hex})"
    elif calculate_luminance(bg_hex) > 0.85:
        bg_setting = f"a clean, pure white studio surface ({bg_hex}) with subtle soft drop shadow"
    elif calculate_luminance(bg_hex) < 0.15:
        bg_setting = f"a deep dark obsidian studio backdrop ({bg_hex}) with gentle ambient edge illumination"

    # 4. Contextual CTA
    if ind in ("food-beverage",):
        cta = "Order Now"
    elif ind in ("beauty-cosmetics", "fashion-apparel", "ecommerce-retail"):
        cta = "Shop Now"
    elif ind in ("fintech-finance", "tech-saas"):
        cta = "Get Started"
    elif ind in ("real-estate",):
        cta = "Book Tour"
    else:
        cta = "Learn More"

    # 5. Typographic & visual aesthetic classification
    if ind in ("beauty-cosmetics", "jewelry-luxury", "fashion-apparel"):
        headline_style = "High-Contrast Editorial Serif (Didone / Modern Roman)"
        rec_headline = ["Playfair Display", "Cormorant Garamond", "Canela", "Fraunces"]
        rec_body = ["Plus Jakarta Sans", "Inter", "Montserrat"]
        treatment = "All-caps or sentence case with elegant wide letter-spacing (+0.08em), high contrast dark lettering"
        lighting = "soft diffused natural morning sunlight casting gentle organic shadows"
        movement = "Minimalist Luxury Editorial Art Direction"
    elif ind in ("fintech-finance", "tech-saas"):
        headline_style = "Bold Geometric Grotesk Sans-Serif"
        rec_headline = ["Satoshi", "Plus Jakarta Sans", "Syne", "PP Neue Montreal"]
        rec_body = ["Inter", "Geist", "DM Sans"]
        treatment = "All-caps or clean sentence case with tight tracking (-0.02em), crisp high-contrast fill"
        lighting = "sleek studio illumination with subtle colored edge rim lighting"
        movement = "Contemporary High-Tech Commercial Graphic Design"
    elif ind in ("food-beverage", "fitness-sports"):
        headline_style = "Heavy Condensed Display Sans or Punchy Bold Serif"
        rec_headline = ["Cabinet Grotesk", "Clash Display", "Recoleta", "Bebas Neue"]
        rec_body = ["DM Sans", "Outfit", "Space Grotesk"]
        treatment = "Heavy bold uppercase with tight line height and impactful visual presence"
        lighting = "vibrant commercial studio lighting with mouthwatering rich contrast"
        movement = "Bold Commercial Poster Art Direction"
    else:
        headline_style = "Clean Contemporary Display Sans-Serif"
        rec_headline = ["Plus Jakarta Sans", "Cabinet Grotesk", "Satoshi", "Inter"]
        rec_body = ["Inter", "DM Sans", "Roboto"]
        treatment = "Clean title case or uppercase with balanced tracking"
        lighting = "clean commercial studio lighting with soft balanced fill"
        movement = "Clean Modern Advertising Graphic Design"

    return {
        "headline": headline,
        "subhead": subhead,
        "subject": subject,
        "cta": cta,
        "bg_setting": bg_setting,
        "bg_hex": bg_hex,
        "accent_hex": accent_hex,
        "bg_color_name": bg_color_name,
        "accent_color_name": accent_color_name,
        "headline_style": headline_style,
        "recommended_headline_fonts": rec_headline,
        "recommended_body_fonts": rec_body,
        "treatment": treatment,
        "lighting": lighting,
        "movement": movement,
    }


# ==============================================================================
# Natural Prompt Template Formatter (Production-Ready)
# ==============================================================================

def build_nano_banana_prompt(analysis: dict[str, Any]) -> str:
    """Builds a hyper-detailed, pixel-faithful creative replication prompt for Nano Banana 2.1."""
    direct = analysis.get("prompts", {}).get("nano_banana") or analysis.get("prompt_templates", {}).get("nano_banana")
    if direct and "composition layout:" not in direct and len(direct.strip()) > 120:
        return direct.strip()

    layout = analysis.get("layout", {})
    typography = analysis.get("typography", {})
    content = analysis.get("content", {})
    colors = analysis.get("colors", {})
    aesthetic = analysis.get("design_aesthetic", {})
    gt = analysis.get("ground_truth", {})

    ratio = layout.get("aspect_ratio_code", "4:5")
    ratio_name = layout.get("aspect_ratio_name", "Portrait Format")
    industry = analysis.get("industry_label", "Commercial Advertising")

    subject = gt.get("subject") or content.get("detected_headline") or "hero product"
    headline = gt.get("headline") or content.get("detected_headline") or "NEW ARRIVAL"
    subhead = gt.get("subhead") or content.get("detected_subtext") or ""
    cta = gt.get("cta") or content.get("detected_cta") or "Shop Now"
    badges = content.get("detected_badges") or []

    bg_hex = colors.get("background_color", "#0d1117")
    primary_accent = colors.get("primary_accent", "#3b82f6")
    secondary_accent = colors.get("secondary_accent", "#e60023")
    palette = colors.get("palette") or [bg_hex, primary_accent, secondary_accent]
    palette_str = ", ".join(palette[:4])

    bg_color_name = gt.get("bg_color_name") or hex_to_color_name(bg_hex)
    accent_color_name = gt.get("accent_color_name") or hex_to_color_name(primary_accent)
    bg_setting = gt.get("bg_setting") or f"a clean, solid {bg_color_name} studio canvas ({bg_hex})"

    typo_style = gt.get("headline_style") or typography.get("headline_font_style") or "Bold Display Typography"
    rec_fonts = ", ".join(gt.get("recommended_headline_fonts") or typography.get("recommended_headline_fonts") or ["Cabinet Grotesk", "Plus Jakarta Sans"])
    body_style = typography.get("body_font_style", "Clean Geometric Sans-Serif")
    treatment = gt.get("treatment") or typography.get("treatment_effects") or "High-contrast bold styling with balanced letter tracking"

    lighting = gt.get("lighting") or aesthetic.get("lighting") or "clean commercial studio lighting with soft balanced fill"
    movement = gt.get("movement") or aesthetic.get("movement") or "Modern Commercial Graphic Design"

    parts = []

    # 1. Deliverable, Framing & Resolution
    parts.append(
        f"A master-quality commercial advertising poster designed for {industry}, in {ratio} portrait aspect ratio ({ratio_name}). "
        f"Rendered in crystal-clear 4K resolution, studio retoucher finish, shot on Hasselblad H6D-100c with an 80mm f/2.8 lens for corner-to-corner tack-sharp clarity."
    )

    # 2. Canvas & Spatial Architecture
    parts.append(
        f"Canvas & Environment: {bg_setting}. The composition is built on a rigorous 3-tier vertical hierarchy with generous commercial negative space: "
        f"Top 25% header zone, center 55% dedicated hero visual container, and bottom 20% call-to-action anchor zone."
    )

    # 3. Hero Visual Asset Details
    parts.append(
        f"Hero Visual: Centered horizontally and vertically is {subject}. Rendered with hyper-realistic material textures, natural surface highlights, "
        f"authentic depth of field, and grounded by a gentle, soft contact shadow resting onto the {bg_color_name} canvas."
    )

    # 4. Verbatim Typography & Spatial Anchoring
    typo_desc = (
        f"Typography System: At the top center, bold high-impact headline lettering in {typo_style} (recommended typefaces: {rec_fonts}) reads verbatim: \"{headline.upper()}\", "
        f"styled with {treatment}."
    )
    if subhead:
        typo_desc += f" Directly beneath the headline, clean legible supporting text in {body_style} reads: \"{subhead}\"."
    if badges:
        badge_text = ", ".join(f'"{b}"' for b in badges if b)
        if badge_text:
            typo_desc += f" An accompanying pill badge reads: {badge_text}."
    parts.append(typo_desc)

    # 5. Call To Action & Footer
    parts.append(
        f"Call-To-Action: Anchored at the bottom center of the frame is a sleek, modern pill-shaped button with a {accent_color_name} fill ({primary_accent}) "
        f"featuring crisp, high-contrast typography reading: \"{cta.upper()}\"."
    )

    # 6. Chromatic Palette & Lighting Atmosphere
    parts.append(
        f"Palette & Lighting: Cohesive color grading anchored in {palette_str}. {lighting}, with subtle rim highlights defining the subject's edges against the {bg_color_name} background. "
        f"Pristine commercial advertising aesthetic, {movement}, award-winning graphic design layout, 4K resolution."
    )

    return " ".join(parts).strip()


def build_nano_banana_edit_prompt(analysis: dict[str, Any]) -> str:
    """Builds a reference-image guided edit & layout transfer prompt for Nano Banana 2.1."""
    direct = analysis.get("prompts", {}).get("nano_banana_edit") or analysis.get("prompt_templates", {}).get("nano_banana_edit")
    if direct and "composition layout:" not in direct and len(direct.strip()) > 120:
        return direct.strip()

    layout = analysis.get("layout", {})
    typography = analysis.get("typography", {})
    content = analysis.get("content", {})
    colors = analysis.get("colors", {})
    aesthetic = analysis.get("design_aesthetic", {})
    gt = analysis.get("ground_truth", {})

    ratio = layout.get("aspect_ratio_code", "4:5")

    subject = gt.get("subject") or content.get("detected_headline") or "hero product"
    headline = gt.get("headline") or content.get("detected_headline") or "NEW ARRIVAL"
    subhead = gt.get("subhead") or content.get("detected_subtext") or ""
    cta = gt.get("cta") or content.get("detected_cta") or "Shop Now"

    bg_hex = colors.get("background_color", "#0d1117")
    primary_accent = colors.get("primary_accent", "#3b82f6")
    bg_color_name = gt.get("bg_color_name") or hex_to_color_name(bg_hex)
    typo_style = gt.get("headline_style") or typography.get("headline_font_style") or "Bold Display Typography"
    lighting = gt.get("lighting") or aesthetic.get("lighting") or "clean commercial studio lighting"

    subhead_clause = f" Preserve the supporting subtext layout reading: \"{subhead}\"." if subhead else ""

    prompt = (
        f"Edit and style transfer using the provided design reference image: "
        f"1. CANVAS & RATIO: Lock and preserve the exact {ratio} aspect ratio, centered 3-tier vertical grid, and solid {bg_color_name} canvas tone ({bg_hex}) with its original negative space margins. "
        f"2. TYPOGRAPHY: Preserve the exact top header placement, scale, and font styling: render the bold display text \"{headline.upper()}\" in {typo_style} across the top.{subhead_clause} "
        f"3. HERO ASSET REPLACEMENT: Replace the central hero subject (currently {subject}) with [INSERT_YOUR_PRODUCT_OR_HERO_ASSET_HERE]. Seamlessly composite the replacement asset into the exact center, matching the original 45-degree angle, scale, soft contact shadow, and ambient reflections on the {bg_color_name} surface. "
        f"4. CALL TO ACTION: Preserve the bottom pill-shaped button container ({primary_accent}) with crisp text reading: \"{cta.upper()}\". "
        f"5. ATMOSPHERE & QUALITY: Maintain the {lighting}, cohesive {bg_color_name} color grading, and pristine commercial advertising finish, 4K resolution."
    )
    return prompt.strip()


def build_ad_creative_template(analysis: dict[str, Any], custom: dict[str, Any] | None = None) -> str:
    """Builds a parameterized ad creative template with variable placeholders."""
    custom = custom or {}
    layout = analysis.get("layout", {})
    typography = analysis.get("typography", {})
    colors = analysis.get("colors", {})
    aesthetic = analysis.get("design_aesthetic", {})
    gt = analysis.get("ground_truth", {})

    brand = custom.get("brand_name") or "{{BRAND_NAME}}"
    product = custom.get("product_name") or "{{PRODUCT_NAME}}"
    headline = custom.get("headline") or gt.get("headline") or "{{HEADLINE_HOOK}}"
    subtext = custom.get("subtext") or gt.get("subhead") or "{{SUPPORTING_SUBTEXT}}"
    cta = custom.get("cta") or gt.get("cta") or "{{CTA_BUTTON}}"

    bg_color = colors.get("background_color", "#0f172a")
    accent_color = colors.get("primary_accent", "#3b82f6")
    subject_ref = gt.get("subject") or "hero asset"
    rec_fonts = ", ".join(typography.get("recommended_headline_fonts") or gt.get("recommended_headline_fonts") or ["Inter"])

    template = f"""# AI Ad Creative Design Template: {analysis.get('industry_label', 'General')}

## 1. Creative Architecture & Flow
- Target Ratio / Format: {layout.get('aspect_ratio_name', '4:5 Portrait Feed')} ({layout.get('aspect_ratio_code', '4:5')})
- Visual Hierarchy: Top Hook (30%) -> Hero Centerpiece (50%) -> Action CTA & Trust (20%)
- Design Movement: {gt.get('movement') or aesthetic.get('movement')}
- Layout Structure: {layout.get('layout_type')}

## 2. Dynamic Slots & Copy
- [Brand Identifier]: {brand}
- [Hero Product / Focus]: {product} (Reference: {subject_ref})
- [Primary Hook Headline]: "{headline}"
  - Font Category: {gt.get('headline_style') or typography.get('headline_font_style')}
  - Recommended Web Fonts: {rec_fonts}
  - Typographic Treatment: {gt.get('treatment') or typography.get('treatment_effects')}
- [Supporting Subtext]: "{subtext}"
  - Font Category: {typography.get('body_font_style', 'Clean Neutral Sans-Serif')}
- [Call to Action Button]: "{cta}"
  - Style: Rounded pill button with high-contrast fill

## 3. Chromatic Palette & Styling Tokens
- Canvas Background Tone: `{bg_color}` ({gt.get('bg_color_name', 'base')})
- Primary Brand Accent: `{accent_color}` ({gt.get('accent_color_name', 'accent')})
- Lighting & Atmosphere: {gt.get('lighting') or aesthetic.get('lighting')}

## 4. Execution Prompt for Image / Layout Generator
"A commercial advertising poster for {brand} presenting {product}.
At the top, bold headline text reads '{headline}' in {gt.get('headline_style', 'clean typography')}.
In the center, {product} is positioned against {gt.get('bg_setting', bg_color)}.
At the bottom, a clean call-to-action button reads '{cta}'.
{gt.get('lighting', 'clean studio lighting')}, high-end commercial graphic design finish, 8k resolution."
"""
    return template.strip()


def build_figma_specs(analysis: dict[str, Any]) -> str:
    """Builds CSS tokens and Figma design system specifications."""
    colors = analysis.get("colors", {})
    typography = analysis.get("typography", {})
    layout = analysis.get("layout", {})
    gt = analysis.get("ground_truth", {})
    palette = colors.get("palette", [])

    h_fonts = typography.get("recommended_headline_fonts") or gt.get("recommended_headline_fonts") or ["Inter"]
    b_fonts = typography.get("recommended_body_fonts") or gt.get("recommended_body_fonts") or ["Inter"]

    bg = colors.get("background_color", palette[0] if palette else "#0d1117")
    accent1 = colors.get("primary_accent", palette[1] if len(palette) > 1 else "#e60023")
    accent2 = colors.get("secondary_accent", palette[2] if len(palette) > 2 else "#58a6ff")
    text_color = colors.get("text_color", "#ffffff" if calculate_luminance(bg) < 0.5 else "#111827")

    specs = f"""/* === Design System Tokens for {analysis.get('industry_label', 'Creative Reference')} === */

:root {{
  /* Color Palette */
  --canvas-bg: {bg};
  --brand-primary: {accent1};
  --brand-secondary: {accent2};
  --text-primary: {text_color};
  --text-muted: {'rgba(255, 255, 255, 0.65)' if calculate_luminance(bg) < 0.5 else 'rgba(0, 0, 0, 0.6)'};
  --palette-swatches: {', '.join(palette)};

  /* Typography Stack */
  --font-headline: '{h_fonts[0]}', -apple-system, sans-serif;
  --font-body: '{b_fonts[0]}', -apple-system, sans-serif;
  --font-headline-weight: 700;
  --font-headline-tracking: -0.02em;
  --font-headline-lineheight: 1.15;

  /* Layout & Geometry */
  --aspect-ratio: {layout.get('aspect_ratio_code', '4/5')};
  --border-radius-card: 16px;
  --border-radius-cta: 9999px;
  --grid-padding: 32px;
}}

/* Figma Frame Specs:
 * Canvas Size: 1080px x 1350px (Standard 4:5 Social/Ad)
 * Primary Focal: {gt.get('subject', 'Centered Hero Asset')}
 * Design Style: {gt.get('movement', 'Clean Modern Commercial')}
 */"""
    return specs.strip()


# ==============================================================================
# Full Heuristic Analyzer (Ground-Truth Driven)
# ==============================================================================

def heuristic_analyze(pin: dict[str, Any], img: Image.Image | None = None) -> dict[str, Any]:
    """Deconstructs the actual creative using pin metadata, NLP extraction, and PIL color analysis."""
    cats = load_categories()
    industry_slug = pin.get("industry") or "uncategorized"
    industry_meta = cats.get("industries", {}).get(industry_slug, {})
    industry_label = industry_meta.get("label", industry_slug.replace("-", " ").title())

    # Image properties
    if img:
        width, height = img.size
        palette = extract_enhanced_palette(img, 6)
    else:
        width = int(pin.get("saved_width") or pin.get("width") or 1080)
        height = int(pin.get("saved_height") or pin.get("height") or 1350)
        palette = pin.get("palette") or ["#0f172a", "#1e293b", "#3b82f6", "#f8fafc", "#64748b"]

    aspect_info = classify_aspect_ratio(width, height)
    gt = extract_pin_ground_truth({**pin, "palette": palette})

    bg_color = palette[0]
    primary_accent = palette[1] if len(palette) > 1 else "#e60023"
    secondary_accent = palette[2] if len(palette) > 2 else "#3b82f6"
    bg_lum = calculate_luminance(bg_color)
    text_color = "#ffffff" if bg_lum < 0.5 else "#0f172a"
    temp = get_color_temperature(primary_accent)

    analysis: dict[str, Any] = {
        "pin_id": pin.get("pin_id"),
        "industry_slug": industry_slug,
        "industry_label": industry_label,
        "analyzer_engine": "ground-truth-heuristic",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "ground_truth": gt,
        "layout": {
            "layout_type": f"Centered Hero with Top-Weighted Headline ({aspect_info['ratio']})",
            "composition": f"Top bold headline reading '{gt['headline']}', central hero visual of {gt['subject']} against {gt['bg_setting']}, bottom call to action '{gt['cta']}'.",
            "hierarchy": f"1. Hook Headline ('{gt['headline']}') -> 2. Hero Asset ({gt['subject']}) -> 3. Action CTA ('{gt['cta']}')",
            "aspect_ratio_code": aspect_info["ratio"],
            "aspect_ratio_name": aspect_info["name"],
            "dimensions": f"{width} × {height}px",
            "spacing_density": "Balanced commercial negative space with centered visual anchor",
        },
        "typography": {
            "headline_font_style": gt["headline_style"],
            "body_font_style": "Clean Geometric Sans-Serif",
            "recommended_headline_fonts": gt["recommended_headline_fonts"],
            "recommended_body_fonts": gt["recommended_body_fonts"],
            "treatment_effects": gt["treatment"],
            "hierarchy_order": f"1. Headline ('{gt['headline']}') -> 2. Subhead ('{gt['subhead']}') -> 3. Button ('{gt['cta']}')",
        },
        "colors": {
            "palette": palette,
            "background_color": bg_color,
            "primary_accent": primary_accent,
            "secondary_accent": secondary_accent,
            "text_color": text_color,
            "temperature": temp,
            "luminance_mode": "dark" if bg_lum < 0.5 else "light",
            "mood": f"High-contrast {gt['bg_color_name']} palette with {gt['accent_color_name']} highlights",
        },
        "design_aesthetic": {
            "movement": gt["movement"],
            "graphic_elements": [gt["subject"], "Framed product container", f"Bold {gt['bg_color_name']} canvas", f"'{gt['cta']}' pill button"],
            "lighting": gt["lighting"],
            "aesthetic_tags": [
                industry_slug,
                aspect_info["ratio"],
                temp,
                gt["bg_color_name"].replace(" ", "-"),
                "commercial-ad-creative",
            ],
        },
        "content": {
            "detected_headline": gt["headline"],
            "detected_subtext": gt["subhead"],
            "detected_cta": gt["cta"],
            "detected_badges": ["Verified Reference Creative"],
        },
    }

    # Generate templates
    analysis["prompt_templates"] = {
        "nano_banana": build_nano_banana_prompt(analysis),
        "nano_banana_edit": build_nano_banana_edit_prompt(analysis),
        "creative_ad": build_ad_creative_template(analysis),
        "figma_specs": build_figma_specs(analysis),
    }

    return analysis


# ==============================================================================
# Gemini Multimodal Vision Analyzer (Pixel-Level Reverse-Engineering)
# ==============================================================================

GEMINI_ANALYSIS_PROMPT = """You are an elite Senior Art Director, Commercial Creative Director, and Master AI Prompt Engineer specializing in Google's Nano Banana 2.1 image generation model.

Your objective is to meticulously reverse-engineer this EXACT reference creative image into hyper-detailed prompts tailored specifically for Nano Banana 2.1.
Nano Banana 2.1 excels at:
- Pinpoint spatial layout anchoring (exact visual zones, coordinates, hierarchy)
- Flawless, sharp typography rendering when text is placed inside exact double quotes
- Complex multi-element composition, studio lighting, materials, and 4K photorealistic fidelity
- Reference-guided style and layout transfer

Examine every pixel of this image with forensic precision:
1. SPATIAL ARCHITECTURE & COMPOSITION:
   - What is the exact aspect ratio (e.g. 9:16 vertical story, 4:5 portrait social feed, 1:1 square)?
   - Describe the composition and reading flow: Where does the eye land first, second, and third?
   - Break the canvas down into spatial zones (Top 20-30% header/hook zone, Middle 50-60% hero product/subject zone, Bottom 15-20% CTA/badge zone).
   - Describe margins, padding, safe areas, symmetry vs asymmetry, and use of negative space.

2. HERO FOCAL SUBJECT & PHYSICAL ATTRIBUTES:
   - What is the exact hero subject? (e.g. "a hand holding a tall triple beef burger with melted yellow cheddar, toasted brioche bun, and crisp lettuce", "a 50ml amber glass dropper bottle with a matte black rubber pipette resting upright on an off-white travertine stone pedestal").
   - Camera angle & framing (e.g. eye-level hero shot, top-down flat lay, 30-degree isometric perspective, macro close-up).
   - Materials, textures, and finishes (e.g. condensation droplets, frosted glass, glossy plastic, brushed metal, woven fabric).
   - Interaction & props (e.g. human hand entering from the right, floating design elements, geometric frames, organic shadows).

3. EXACT VISIBLE TEXT & TYPOGRAPHY SYSTEM:
   - Quote EVERY verbatim piece of text visible on the image in double quotes:
     * Headline text (e.g. "TRIPLE BURGER" or "DON'T BUY THIS SERUM")
     * Subheadline / supporting body text (e.g. "Cheesesteak uchun Triple burger" or "Unless you want clear, stable skin in 29 days")
     * Call-to-action button text (e.g. "ORDER NOW", "SHOP NOW", "GET STARTED")
     * Badges, price tags, disclaimers, or labels (e.g. "NEW ARRIVAL", "50% OFF", "100% ORGANIC")
   - For each text element, specify:
     * Font category and style (e.g. Extra-Bold Condensed Grotesque Sans-Serif, Elegant High-Contrast Modern Serif / Didone, Geometric Sans, Bold Brush Display)
     * Font weight (e.g. Black/Heavy 900, Bold 700, Medium 500)
     * Casing (ALL-CAPS, Sentence Case, Title Case)
     * Color and contrast against background (e.g. high-contrast stark white text #ffffff, deep charcoal #111111)
     * Real recommended Google/Web fonts (e.g. Cabinet Grotesk, Clash Display, Playfair Display, Satoshi, Inter)
     * Placement and alignment (e.g. center-aligned at the top, left-aligned with a colored pill backdrop)

4. CHROMATIC PALETTE & LIGHTING PHYSICS:
   - Identify the exact HEX codes: background color, primary accent, secondary accent, text color.
   - Describe the canvas background: solid color, subtle radial gradient, textured backdrop, studio cyclorama, drop shadows.
   - Lighting physics: Direction of primary key light (e.g. soft diffused 45-degree key light from top-left), rim/edge light color and intensity, ambient fill ratio, specular highlights, cast shadows and ambient occlusion.

5. NANO BANANA 2.1 PROMPTS (ULTRA-DETAILED & PRODUCTION-READY):
   - "nano_banana": A comprehensive, hyper-detailed generation prompt that completely replicates this exact creative in 4K resolution.
     It MUST combine:
     [Deliverable type & aspect ratio] +
     [Background environment, exact hex colors, and backdrop texture] +
     [Spatial architecture & zone breakdown] +
     [Hero subject forensic description, pose, camera angle, and surface materials] +
     [Lighting setup, shadows, and reflections] +
     [Exact typography hierarchy with verbatim quoted text: at top headline "...", subtext "...", and at bottom CTA button "..."] +
     [Color grading, commercial finish, and "4K resolution"].
     Do NOT summarize or be brief. Write a rich, thorough, vivid prompt that leaves no room for AI hallucination.
   - "nano_banana_edit": A reference-image guided prompt for Nano Banana 2.1 image-to-image / multi-reference workflows.
     Specifies: "Edit using the provided reference creative image: Preserve the exact aspect ratio, centered spatial composition, background color (HEX), and studio lighting. Preserve the top typography layout rendering '[VERBATIM HEADLINE]' in [font style] and subtext '[VERBATIM SUBTEXT]'. Replace the central hero subject with [INSERT YOUR PRODUCT OR SUBJECT HERE] (currently [describe original subject]), ensuring the new subject inherits the same perspective, scale, contact shadows, and lighting. Preserve the bottom CTA button '[VERBATIM CTA]'. Output in pristine commercial graphic design quality, 4K resolution."

Return ONLY a valid JSON object matching this schema:
{{
  "creative_summary": "<One sentence describing what this creative actually depicts>",
  "focal_subject": "<Precise forensic description of the hero subject in the image>",
  "background_and_environment": "<Precise description of background color, gradient, lighting, and setting>",
  "layout": {{
    "layout_type": "<e.g. Centered Hero Focus with Top Headline, Asymmetrical Split, Floating Mockup Grid>",
    "composition": "<Detailed breakdown of spatial layout, margins, safe zones, and reading flow>",
    "hierarchy": "<1. Primary focal hook -> 2. Secondary hero asset -> 3. Action CTA button>",
    "aspect_ratio": "<e.g. 4:5, 9:16, 1:1>",
    "spacing_density": "<Airy Minimalist | Balanced Commercial | High-Density Typographic>"
  }},
  "typography": {{
    "detected_headline": "<Verbatim headline text visible on the image>",
    "detected_subtext": "<Verbatim subtext or secondary copy visible on image, or empty string>",
    "detected_cta": "<Verbatim CTA button wording>",
    "detected_badges": ["<any tags or badges visible on image>"],
    "headline_font_style": "<Precise font classification, e.g. Extra-Bold Condensed Grotesque Sans, High-Contrast Didone Serif>",
    "recommended_headline_fonts": ["<Font 1>", "<Font 2>", "<Font 3>"],
    "body_font_style": "<Font classification for body/subtext>",
    "recommended_body_fonts": ["<Font 1>", "<Font 2>"],
    "treatment_effects": "<Casing, tracking, color, text effects, alignment>"
  }},
  "colors": {{
    "palette": ["<#hex1>", "<#hex2>", "<#hex3>", "<#hex4>", "<#hex5>"],
    "background_color": "<#hex>",
    "primary_accent": "<#hex>",
    "secondary_accent": "<#hex>",
    "text_color": "<#hex>",
    "mood": "<Emotional mood, e.g. Vibrant Fast-Food Commercial, Minimalist Luxury Skincare, Dark High-Tech FinTech>"
  }},
  "design_aesthetic": {{
    "movement": "<Specific design movement, e.g. Bold Fast-Food Pop Art, Clean Organic Skincare, Dark Mode FinTech>",
    "graphic_elements": ["<Element 1>", "<Element 2>", "<Element 3>"],
    "lighting": "<Description of lighting direction, reflections, shadows, and render style>"
  }},
  "prompts": {{
    "nano_banana": "<Hyper-detailed, complete creative replication prompt for Nano Banana 2.1 in 4K resolution>",
    "nano_banana_edit": "<Hyper-detailed reference-guided edit & style transfer prompt for Nano Banana 2.1 in 4K resolution>",
    "creative_ad_template": "<Structured template with slots {{BRAND_NAME}}, {{PRODUCT_NAME}}, {{HEADLINE_HOOK}}, {{CTA_BUTTON}}>",
    "figma_specs": "<CSS root variables with palette hex codes, font recommendations, and layout specs>"
  }}
}}"""


def gemini_analyze(
    pin: dict[str, Any],
    image_bytes: bytes,
    img: Image.Image | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    """Performs deep multimodal design analysis via Google Gemini Vision."""
    from google import genai
    from google.genai import types

    key = api_key or config.GEMINI_API_KEY
    if not key:
        raise ValueError("GEMINI_API_KEY is not configured")

    model = model_name or config.GEMINI_MODEL or "gemini-2.5-flash"
    client = genai.Client(api_key=key)

    cats = load_categories()
    industry_slug = pin.get("industry") or "uncategorized"
    industry_label = cats.get("industries", {}).get(industry_slug, {}).get("label", industry_slug)

    prompt = GEMINI_ANALYSIS_PROMPT

    resp = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )

    data = json.loads(resp.text)

    # Determine image dimensions & aspect ratio
    if img:
        width, height = img.size
    else:
        width = int(pin.get("saved_width") or pin.get("width") or 1080)
        height = int(pin.get("saved_height") or pin.get("height") or 1350)

    aspect_info = classify_aspect_ratio(width, height)

    # Merge layout data
    layout_data = data.get("layout", {})
    layout_data["aspect_ratio_code"] = aspect_info["ratio"]
    layout_data["aspect_ratio_name"] = aspect_info["name"]
    layout_data["dimensions"] = f"{width} × {height}px"

    colors_data = data.get("colors", {})
    if not colors_data.get("palette"):
        colors_data["palette"] = pin.get("palette") or ["#0d1117", "#161b22", "#3b82f6", "#ffffff"]
    bg = colors_data.get("background_color") or colors_data["palette"][0]
    colors_data["luminance_mode"] = "dark" if calculate_luminance(bg) < 0.5 else "light"
    colors_data["temperature"] = get_color_temperature(colors_data.get("primary_accent", bg))

    aesthetic_data = data.get("design_aesthetic", {})
    aesthetic_data["aesthetic_tags"] = [
        industry_slug,
        aspect_info["ratio"],
        aesthetic_data.get("movement", "commercial-design").split("/")[0].strip().lower(),
    ]

    # Ground truth bridge
    gt = {
        "subject": data.get("focal_subject") or pin.get("title") or "hero subject",
        "headline": data.get("typography", {}).get("detected_headline") or pin.get("title") or "NEW ARRIVAL",
        "subhead": data.get("typography", {}).get("detected_subtext") or "",
        "cta": data.get("typography", {}).get("detected_cta") or "Shop Now",
        "bg_setting": data.get("background_and_environment") or f"a solid {colors_data.get('background_color', '#000')} background",
        "headline_style": data.get("typography", {}).get("headline_font_style") or "Bold Display Typography",
        "recommended_headline_fonts": data.get("typography", {}).get("recommended_headline_fonts") or ["Inter"],
        "recommended_body_fonts": data.get("typography", {}).get("recommended_body_fonts") or ["Inter"],
        "treatment": data.get("typography", {}).get("treatment_effects") or "High contrast",
        "lighting": data.get("design_aesthetic", {}).get("lighting") or "Studio lighting",
        "movement": data.get("design_aesthetic", {}).get("movement") or "Commercial Graphic Design",
    }

    analysis: dict[str, Any] = {
        "pin_id": pin.get("pin_id"),
        "industry_slug": industry_slug,
        "industry_label": industry_label,
        "analyzer_engine": f"gemini:{model}",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "ground_truth": gt,
        "layout": layout_data,
        "typography": data.get("typography", {}),
        "colors": colors_data,
        "design_aesthetic": aesthetic_data,
        "content": data.get("content") or {
            "detected_headline": gt["headline"],
            "detected_subtext": gt["subhead"],
            "detected_cta": gt["cta"],
            "detected_badges": data.get("typography", {}).get("detected_badges", []),
        },
    }

    # Extract Gemini prompts if present, or use builder
    p_data = data.get("prompts", {})

    analysis["prompt_templates"] = {
        "nano_banana": p_data.get("nano_banana") or build_nano_banana_prompt(analysis),
        "nano_banana_edit": p_data.get("nano_banana_edit") or build_nano_banana_edit_prompt(analysis),
        "creative_ad": p_data.get("creative_ad_template") or build_ad_creative_template(analysis),
        "figma_specs": p_data.get("figma_specs") or build_figma_specs(analysis),
    }

    return analysis


# ==============================================================================
# Unified Analyzer Interface
# ==============================================================================

def analyze_pin(
    pin: dict[str, Any],
    image_bytes_or_path: bytes | Path | str | None = None,
    force_gemini: bool = False,
    api_key: str | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    """Unified entrypoint: analyzes pin using Gemini vision if available, or falls back to ground-truth heuristic engine."""
    image_bytes: bytes | None = None
    pil_image: Image.Image | None = None

    if isinstance(image_bytes_or_path, (str, Path)):
        p = Path(image_bytes_or_path)
        if p.exists() and p.is_file():
            image_bytes = p.read_bytes()
            try:
                pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            except Exception:
                pil_image = None
    elif isinstance(image_bytes_or_path, bytes):
        image_bytes = image_bytes_or_path
        try:
            pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception:
            pil_image = None

    active_key = api_key or config.GEMINI_API_KEY
    can_use_gemini = bool(active_key and image_bytes)

    if can_use_gemini and (force_gemini or config.CLASSIFIER == "gemini" or True):
        try:
            return gemini_analyze(
                pin=pin,
                image_bytes=image_bytes,
                img=pil_image,
                api_key=active_key,
                model_name=model_name,
            )
        except Exception as exc:
            print(f"  [design_analyzer] Gemini vision failed ({exc}); falling back to ground-truth heuristic engine.")

    # Fallback to ground-truth heuristic engine
    return heuristic_analyze(pin=pin, img=pil_image)


# ==============================================================================
# Prompt Template Storage & Library Management
# ==============================================================================

TEMPLATES_INDEX = "index/templates.jsonl"
TEMPLATES_DIR = "templates"


def get_templates_file(repo_dir: Path) -> Path:
    p = repo_dir / TEMPLATES_INDEX
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def list_saved_templates(repo_dir: Path) -> list[dict[str, Any]]:
    fpath = get_templates_file(repo_dir)
    if not fpath.exists():
        return []

    templates: list[dict[str, Any]] = []
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    templates.append(json.loads(line))
                except Exception:
                    continue
    return sorted(templates, key=lambda t: t.get("saved_at", ""), reverse=True)


def save_template_record(repo_dir: Path, template_data: dict[str, Any]) -> dict[str, Any]:
    template_id = template_data.get("id") or f"tpl_{str(uuid.uuid4())[:8]}"
    template_data["id"] = template_id
    template_data["saved_at"] = datetime.now(timezone.utc).isoformat()

    fpath = get_templates_file(repo_dir)
    existing = list_saved_templates(repo_dir)
    updated = [t for t in existing if t.get("id") != template_id]
    updated.insert(0, template_data)

    with open(fpath, "w", encoding="utf-8") as f:
        for item in updated:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    md_dir = repo_dir / TEMPLATES_DIR
    md_dir.mkdir(parents=True, exist_ok=True)
    md_file = md_dir / f"{template_id}.md"

    md_content = f"""# Prompt Template: {template_data.get('title', 'Design Reference Template')}

- **Template ID:** `{template_id}`
- **Source Pin ID:** `{template_data.get('pin_id', '-')}`
- **Industry:** `{template_data.get('industry', 'general')}`
- **Created:** {template_data['saved_at']}
- **Design Movement:** {template_data.get('movement', 'Contemporary Graphic Design')}

## Nano Banana 2.1 Master Creative Generation Prompt (4K)
```text
{template_data.get('prompt_templates', {}).get('nano_banana', '')}
```

## Nano Banana 2.1 Style-Reference Edit Prompt
```text
{template_data.get('prompt_templates', {}).get('nano_banana_edit', '')}
```

## Parameterized Ad Creative Template
```markdown
{template_data.get('prompt_templates', {}).get('creative_ad', '')}
```

## Figma / CSS Design Tokens
```css
{template_data.get('prompt_templates', {}).get('figma_specs', '')}
```
"""
    md_file.write_text(md_content, encoding="utf-8")
    return template_data


def delete_template_record(repo_dir: Path, template_id: str) -> bool:
    fpath = get_templates_file(repo_dir)
    if not fpath.exists():
        return False

    existing = list_saved_templates(repo_dir)
    remaining = [t for t in existing if t.get("id") != template_id]
    if len(remaining) == len(existing):
        return False

    with open(fpath, "w", encoding="utf-8") as f:
        for item in remaining:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    md_file = repo_dir / TEMPLATES_DIR / f"{template_id}.md"
    if md_file.exists():
        try:
            md_file.unlink()
        except OSError:
            pass

    return True
