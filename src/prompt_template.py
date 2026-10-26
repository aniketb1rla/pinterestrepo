"""Command-line tool to analyze pins and generate AI design prompt templates.

Usage:
    # Analyze a specific pin and view all prompt templates
    python -m src.prompt_template 1000291767255653778

    # Generate a specific format (nano-banana | creative | figma | all)
    python -m src.prompt_template 1000291767255653778 --format nano-banana

    # Parameterize ad template with brand and product
    python -m src.prompt_template 1000291767255653778 --brand "Acme Glow" --product "Vitamin C Serum"

    # Save generated template to templates library
    python -m src.prompt_template 1000291767255653778 --save

    # List all saved prompt templates
    python -m src.prompt_template --list

    # Export markdown report to a file
    python -m src.prompt_template 1000291767255653778 --output my_prompt.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import config
from .design_analyzer import (
    analyze_pin,
    build_ad_creative_template,
    delete_template_record,
    list_saved_templates,
    save_template_record,
)


def load_all_pins(repo_dir: Path) -> dict[str, dict[str, Any]]:
    pins_file = repo_dir / "index" / "pins.jsonl"
    if not pins_file.exists():
        return {}
    pins = {}
    with open(pins_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    p = json.loads(line)
                    pins[p["pin_id"]] = p
                except Exception:
                    pass
    return pins


def format_cli_output(analysis: dict[str, Any], target_format: str = "all") -> str:
    layout = analysis.get("layout", {})
    typo = analysis.get("typography", {})
    colors = analysis.get("colors", {})
    aesthetic = analysis.get("design_aesthetic", {})
    content = analysis.get("content", {})
    templates = analysis.get("prompt_templates", {})

    lines: list[str] = []

    if target_format in ("all", "summary"):
        lines.append("=" * 70)
        lines.append(f"  DESIGN DNA ANALYSIS: Pin #{analysis.get('pin_id')}")
        lines.append(f"  Industry: {analysis.get('industry_label')} | Engine: {analysis.get('analyzer_engine')}")
        lines.append("=" * 70)
        lines.append("")
        lines.append("[1. LAYOUT & COMPOSITION]")
        lines.append(f"  Structure:     {layout.get('layout_type')}")
        lines.append(f"  Aspect Ratio:  {layout.get('aspect_ratio_name')} ({layout.get('aspect_ratio_code')})")
        lines.append(f"  Hierarchy:     {layout.get('hierarchy')}")
        lines.append(f"  Spacing:       {layout.get('spacing_density')}")
        lines.append("")
        lines.append("[2. TYPOGRAPHY & FONTS]")
        lines.append(f"  Headline Style: {typo.get('headline_font_style')}")
        lines.append(f"  Rec. Fonts:     {', '.join(typo.get('recommended_headline_fonts', []))}")
        lines.append(f"  Body Style:     {typo.get('body_font_style')}")
        lines.append(f"  Treatment:      {typo.get('treatment_effects')}")
        lines.append("")
        lines.append("[3. COLORS & PALETTE]")
        lines.append(f"  Mood:           {colors.get('mood')}")
        lines.append(f"  Canvas:         {colors.get('background_color')} ({colors.get('luminance_mode')} mode)")
        lines.append(f"  Primary Accent: {colors.get('primary_accent')}")
        lines.append(f"  Swatches:       {' '.join(colors.get('palette', []))}")
        lines.append("")
        lines.append("[4. DESIGN AESTHETIC & ELEMENTS]")
        lines.append(f"  Movement:       {aesthetic.get('movement')}")
        lines.append(f"  Key Elements:   {', '.join(aesthetic.get('graphic_elements', []))}")
        lines.append(f"  Lighting:       {aesthetic.get('lighting')}")
        lines.append("")

    if target_format in ("all", "nano-banana", "nano_banana"):
        lines.append("-" * 70)
        lines.append("  NANO BANANA 2.1 GENERATION PROMPT (4K):")
        lines.append("-" * 70)
        lines.append(templates.get("nano_banana", ""))
        lines.append("")
        lines.append("-" * 70)
        lines.append("  NANO BANANA 2.1 REFERENCE-IMAGE EDIT PROMPT:")
        lines.append("-" * 70)
        lines.append(templates.get("nano_banana_edit", ""))
        lines.append("")

    if target_format in ("all", "creative"):
        lines.append("-" * 70)
        lines.append("  AI AD CREATIVE TEMPLATE:")
        lines.append("-" * 70)
        lines.append(templates.get("creative_ad", ""))
        lines.append("")

    if target_format in ("all", "figma"):
        lines.append("-" * 70)
        lines.append("  FIGMA / CSS DESIGN SYSTEM TOKENS:")
        lines.append("-" * 70)
        lines.append(templates.get("figma_specs", ""))
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze Pinterest references and generate design prompt templates.")
    parser.add_argument("pin_id", nargs="?", help="Pin ID to analyze")
    parser.add_argument("--format", choices=["all", "nano-banana", "creative", "figma", "summary"], default="all", help="Prompt template format")
    parser.add_argument("--brand", default="", help="Brand name variable to inject into template")
    parser.add_argument("--product", default="", help="Product name variable to inject into template")
    parser.add_argument("--headline", default="", help="Custom headline hook to inject into template")
    parser.add_argument("--cta", default="", help="Custom CTA button text to inject into template")
    parser.add_argument("--force-gemini", action="store_true", help="Force multimodal Gemini vision analysis")
    parser.add_argument("--save", action="store_true", help="Save the generated prompt template to templates library")
    parser.add_argument("--title", default="", help="Custom title when saving template")
    parser.add_argument("--list", action="store_true", help="List all saved prompt templates")
    parser.add_argument("--delete", metavar="TEMPLATE_ID", help="Delete a saved template by ID")
    parser.add_argument("--output", "-o", metavar="FILE", help="Save output to a text or markdown file")
    parser.add_argument("--json", action="store_true", help="Output raw JSON analysis")

    args = parser.parse_args()
    repo_dir = config.REPO_DIR

    # 1. List saved templates
    if args.list:
        templates = list_saved_templates(repo_dir)
        print(f"\nSaved Prompt Templates ({len(templates)}):")
        print("=" * 70)
        if not templates:
            print("  No saved templates yet. Run: python -m src.prompt_template <pin_id> --save")
        else:
            for t in templates:
                print(f"  [{t.get('id')}] {t.get('title', 'Untitled')} ({t.get('industry', 'general')}) - {t.get('saved_at', '')[:10]}")
        print("")
        return

    # 2. Delete template
    if args.delete:
        ok = delete_template_record(repo_dir, args.delete)
        if ok:
            print(f"✓ Deleted template {args.delete}")
        else:
            print(f"Error: template {args.delete} not found.")
        return

    if not args.pin_id:
        parser.print_help()
        sys.exit(1)

    # 3. Load pin
    pins = load_all_pins(repo_dir)
    pin = pins.get(args.pin_id)
    if not pin:
        print(f"Error: Pin ID '{args.pin_id}' not found in {repo_dir / 'index' / 'pins.jsonl'}")
        sys.exit(1)

    # Resolve image path
    img_rel = pin.get("image_path", "")
    img_path = repo_dir / img_rel if img_rel else None

    # Run analysis
    analysis = analyze_pin(
        pin=pin,
        image_bytes_or_path=img_path,
        force_gemini=args.force_gemini,
    )

    # Apply custom variables if provided
    if args.brand or args.product or args.headline or args.cta:
        custom_vars = {
            "brand_name": args.brand,
            "product_name": args.product,
            "headline": args.headline,
            "cta": args.cta,
        }
        analysis["prompt_templates"]["creative_ad"] = build_ad_creative_template(analysis, custom_vars)

    # Save to library if requested
    if args.save:
        title = args.title or f"{pin.get('title') or analysis.get('industry_label')} Template"
        template_record = {
            "pin_id": pin.get("pin_id"),
            "title": title,
            "industry": analysis.get("industry_slug"),
            "movement": analysis.get("design_aesthetic", {}).get("movement"),
            "aspect_ratio": analysis.get("layout", {}).get("aspect_ratio_code"),
            "prompt_templates": analysis.get("prompt_templates"),
            "colors": analysis.get("colors"),
            "typography": analysis.get("typography"),
            "layout": analysis.get("layout"),
        }
        saved = save_template_record(repo_dir, template_record)
        print(f"✓ Saved template to library: {saved['id']} (pinterestrepo/templates/{saved['id']}.md)")

    # Output formatting
    if args.json:
        out_text = json.dumps(analysis, indent=2, ensure_ascii=False)
    else:
        out_text = format_cli_output(analysis, args.format)

    if args.output:
        Path(args.output).write_text(out_text, encoding="utf-8")
        print(f"✓ Output exported to {args.output}")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
