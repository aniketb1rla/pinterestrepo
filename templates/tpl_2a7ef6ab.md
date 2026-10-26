# Prompt Template: Beauty & Cosmetics Template

- **Template ID:** `tpl_2a7ef6ab`
- **Source Pin ID:** `1000291767255653778`
- **Industry:** `beauty-cosmetics`
- **Created:** 2026-10-23T12:00:23.338820+00:00
- **Design Movement:** Organic Luxury Minimalist / Editorial Skincare Aesthetic

## Midjourney v6.1 Art Direction Prompt
```text
Graphic design advertising creative for Beauty & Cosmetics, Organic Luxury Minimalist / Editorial Skincare Aesthetic, composition layout: Top delicate editorial headline, central premium cosmetic bottle on organic travertine or water pedestal, bottom botanical ingredients notes and soft CTA, typography styling: High-Contrast Editorial Serif or Elegant Modern Didone with Sentence case or wide-tracked all-caps (+0.12em) with elegant italicized emphasis on key adjectives, featuring Don’t buy this serum, design accents: Smooth travertine stone pedestal, Organic sunlight caustics / water ripple reflections, Fresh botanical ingredient leaf, Minimal glass dropper bottle with embossed label, color palette: #f2e8dc, #f1e3d7, #f0e6da, #bd9889 (Serene, pure, rejuvenating, warm organic luxury and clean radiance), lighting: Warm morning sunlight filtering through linen curtains, delicate natural shadows, warm softbox fill, clean negative space, award-winning Behance and Dribbble graphic design reference, 8k render --ar 4:5 --style raw --v 6.1
```

## FLUX.1 / SDXL Prompt
```text
A masterwork graphic design ad creative layout. Style: Organic Luxury Minimalist / Editorial Skincare Aesthetic. Composition: Top delicate editorial headline, central premium cosmetic bottle on organic travertine or water pedestal, bottom botanical ingredients notes and soft CTA. Visual hierarchy: Emotional skincare benefit headline -> Product bottle hero -> Ingredient callout badge -> Soft pill CTA. Headline typography: High-Contrast Editorial Serif or Elegant Modern Didone, text placement: top and center. Main subject: Don’t buy this serum. Color scheme: Dominant #f2e8dc, primary accent #f1e3d7, Serene, pure, rejuvenating, warm organic luxury and clean radiance. Key elements: Smooth travertine stone pedestal, Organic sunlight caustics / water ripple reflections, Fresh botanical ingredient leaf, Minimal glass dropper bottle with embossed label, Soft beige gradient backdrop. Lighting: Warm morning sunlight filtering through linen curtains, delicate natural shadows, warm softbox fill. Pristine commercial graphic design, sharp vectors, balanced margins, high typographic precision, no clutter.
```

## Parameterized Ad Creative Template
```markdown
# AI Ad Creative Design Template: Beauty & Cosmetics

## 1. Creative Architecture
- Target Platform / Aspect: Portrait Feed / Standard Ad (4:5) (4:5)
- Design Movement: Organic Luxury Minimalist / Editorial Skincare Aesthetic
- Layout Structure: Centered Hero Pedestal with Negative Space
- Visual Hierarchy: Emotional skincare benefit headline -> Product bottle hero -> Ingredient callout badge -> Soft pill CTA

## 2. Dynamic Slots & Copy
- [Brand Identifier]: {{BRAND_NAME}}
- [Hero Focus / Asset]: {{PRODUCT_NAME}}
- [Primary Hook Headline]: "Don’t buy this serum"
  - Font Category: High-Contrast Editorial Serif or Elegant Modern Didone
  - Recommended Web Fonts: Playfair Display, Cormorant Garamond, Canela, Fraunces
  - Typographic Treatment: Sentence case or wide-tracked all-caps (+0.12em) with elegant italicized emphasis on key adjectives
- [Supporting Subtext / Value Prop]: "Unless you’re done overcomplicating your skin"
  - Font Category: Ultra-Clean Geometric Sans or Delicate Light Sans
  - Recommended Web Fonts: Plus Jakarta Sans, Montserrat, Jost
- [Call to Action Button]: "Get Started"
  - Style: Rounded pill button, high-contrast fill

## 3. Chromatic Palette & Styling Tokens
- Canvas / Background Tone: `#f2e8dc`
- Primary Brand Accent: `#f1e3d7`
- Color Mood: Serene, pure, rejuvenating, warm organic luxury and clean radiance
- Decorative Elements: Smooth travertine stone pedestal, Organic sunlight caustics / water ripple reflections, Fresh botanical ingredient leaf, Minimal glass dropper bottle with embossed label, Soft beige gradient backdrop
- Studio Lighting: Warm morning sunlight filtering through linen curtains, delicate natural shadows, warm softbox fill

## 4. Execution Prompt for Image / Layout Generator
"Create a 4:5 commercial advertisement for {{BRAND_NAME}} presenting {{PRODUCT_NAME}}.
Headline reads 'Don’t buy this serum' in bold High-Contrast Editorial Serif or Elegant Modern Didone.
Clean subtext 'Unless you’re done overcomplicating your skin'. Prominent CTA badge 'Get Started'.
Aesthetic: Organic Luxury Minimalist / Editorial Skincare Aesthetic.
Color scheme anchored in #f2e8dc with #f1e3d7 accents.
Warm morning sunlight filtering through linen curtains, delicate natural shadows, warm softbox fill, pristine commercial finish."
```

## Figma / CSS Design Tokens
```css
/* === Design System Tokens for Beauty & Cosmetics === */

:root {
  /* Color Palette */
  --canvas-bg: #f2e8dc;
  --brand-primary: #f1e3d7;
  --brand-secondary: #f0e6da;
  --text-primary: #0f172a;
  --text-muted: rgba(0, 0, 0, 0.6);
  --palette-swatches: #f2e8dc, #f1e3d7, #f0e6da, #bd9889, #f3e7db, #f5ece1;

  /* Typography Stack */
  --font-headline: 'Playfair Display', -apple-system, sans-serif;
  --font-body: 'Plus Jakarta Sans', -apple-system, sans-serif;
  --font-headline-weight: 700;
  --font-headline-tracking: -0.02em;
  --font-headline-lineheight: 1.15;

  /* Layout & Geometry */
  --aspect-ratio: 4:5;
  --border-radius-card: 16px;
  --border-radius-cta: 9999px;
  --grid-padding: 32px;
}

/* Figma Frame Specs:
 * Canvas Size: 1080px x 1350px (Standard 4:5 Social/Ad)
 * Grid: 12-column, margin 32px, gutter 16px
 * Primary Focal: Emotional skincare benefit headline -> Product bottle hero -> Ingredient callout badge -> Soft pill CTA
 * Design Style: Organic Luxury Minimalist / Editorial Skincare Aesthetic
 */
```
