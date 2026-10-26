"""Downloader for Pinterest pins and boards.

Downloads pins by Pin URL, Pin ID, pin.it short link, or Board URL.
Can save directly to a local directory (e.g. ./downloads/) and/or
into your reference dataset repository.

Examples:
  # Download a single pin into the dataset
  python -m src.download "https://www.pinterest.com/pin/123456789/"

  # Download high-res image directly to a local folder
  python -m src.download "https://pin.it/abc123" --output ./downloads

  # Download multiple pins by ID with metadata into a folder
  python -m src.download "123456789" "987654321" -o ./pins --save-meta

  # Download a Pinterest board (up to 40 pins)
  python -m src.download "https://www.pinterest.com/username/boardname/" --limit 40

  # Download from a text file containing URLs / IDs
  python -m src.download --file pins.txt -o ./downloads
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import config, git_sync
from .browser import open_context
from .classifier import classify, load_categories
from .collect import download as download_image_bytes
from .scraper import NotLoggedIn, fetch_board_pins, fetch_pin, parse_target, search_pins
from .storage import Dataset, dhash, prepare_image


def save_pin_to_folder(
    ctx,
    pin: dict,
    output_dir: Path,
    save_meta: bool = True,
    industry: str | None = None,
    classifier_mode: str | None = None,
) -> Path | None:
    """Download and save a pin image (and optional metadata) to a local directory."""
    raw = download_image_bytes(ctx, pin["image_url"])
    if not raw:
        print(f"  [{pin['pin_id']}] download image failed: {pin['image_url']}")
        return None

    try:
        jpeg, img = prepare_image(raw)
    except Exception as e:
        print(f"  [{pin['pin_id']}] prepare image failed: {e}")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    pin_id = pin["pin_id"]
    img_path = output_dir / f"{pin_id}.jpg"
    img_path.write_bytes(jpeg)

    if save_meta:
        info = classify(pin, jpeg, force_industry=industry, mode=classifier_mode)
        caption = info.get("caption") or pin.get("description") or pin.get("title") or ""
        txt_path = output_dir / f"{pin_id}.txt"
        txt_path.write_text(caption, encoding="utf-8")

        meta = {
            **{k: v for k, v in pin.items() if not k.startswith("_")},
            **info,
            "saved_image": str(img_path.name),
            "width": img.width,
            "height": img.height,
            "aspect_ratio": round(img.width / img.height, 3) if img.height else 1.0,
        }
        json_path = output_dir / f"{pin_id}.json"
        json_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  ✓ [file] Saved to {img_path} ({img.width}x{img.height})")
    return img_path


def save_pin_to_dataset(
    ctx,
    ds: Dataset,
    pin: dict,
    industry: str | None = None,
    classifier_mode: str | None = None,
    min_side: int = 400,
    include_promoted: bool = False,
) -> bool:
    """Download, classify, and save a pin into the dataset repository."""
    if not include_promoted and pin.get("is_promoted"):
        return False

    raw = download_image_bytes(ctx, pin["image_url"])
    if not raw:
        print(f"  [{pin.get('pin_id', 'pin')}] download image failed")
        return False

    try:
        jpeg, img = prepare_image(raw)
    except Exception:
        return False

    if min(img.size) < min_side:
        print(f"  [{pin.get('pin_id', 'pin')}] image too small ({min(img.size)}px < {min_side}px) — skipped")
        return False

    h = dhash(img)
    if ds.is_duplicate(h):
        print(f"  [{pin.get('pin_id', 'pin')}] duplicate image — skipped")
        return False

    info = classify(pin, jpeg, force_industry=industry, mode=classifier_mode)
    if config.DROP_NON_DESIGN and info.get("is_design") is False:
        print(f"  [{pin.get('pin_id', 'pin')}] plain photo — skipped")
        return False

    ds.add(pin, jpeg, img, h, info)
    print(f"  ✓ {info['industry']:<22} {(pin.get('title') or pin.get('alt_text') or pin.get('pin_id'))[:60]}")
    return True


def download_targets(
    targets: list[str],
    output_dir: Path | None = None,
    save_to_dataset: bool = True,
    industry: str | None = None,
    classifier_mode: str | None = None,
    limit: int = 50,
    min_side: int = 400,
    save_meta: bool = True,
    include_videos: bool = False,
    include_promoted: bool = False,
    headless: bool | None = None,
    no_push: bool = False,
) -> dict[str, Any]:
    """Execute download for a list of targets (Pin URLs, IDs, Board URLs, or keywords)."""
    if industry and industry not in load_categories()["industries"]:
        raise ValueError(f"unknown industry '{industry}'. See config/categories.yaml")

    ds: Dataset | None = None
    repo_path: Path | None = None
    if save_to_dataset:
        repo_path = git_sync.ensure_repo() if not no_push else config.REPO_DIR
        ds = Dataset(repo_path)

    results = {
        "total_attempted": 0,
        "saved_folder": 0,
        "saved_dataset": 0,
        "failed": 0,
        "pins": [],
    }

    with open_context(headless=headless) as ctx:
        for t in targets:
            s = t.strip()
            if not s:
                continue
            parsed = parse_target(s)
            target_type = parsed["type"]

            if target_type in ("pin", "pin_short"):
                results["total_attempted"] += 1
                print(f"\n📌 Downloading pin: {s}")
                pin = fetch_pin(ctx, s)
                if not pin:
                    print(f"  ❌ Could not load pin details for: {s}")
                    results["failed"] += 1
                    continue

                folder_ok = False
                if output_dir:
                    p = save_pin_to_folder(
                        ctx,
                        pin,
                        output_dir,
                        save_meta=save_meta,
                        industry=industry,
                        classifier_mode=classifier_mode,
                    )
                    if p:
                        results["saved_folder"] += 1
                        folder_ok = True

                dataset_ok = False
                if ds:
                    if save_pin_to_dataset(
                        ctx,
                        ds,
                        pin,
                        industry=industry,
                        classifier_mode=classifier_mode,
                        min_side=min_side,
                        include_promoted=include_promoted,
                    ):
                        results["saved_dataset"] += 1
                        dataset_ok = True
                    ds.write_stats()

                if folder_ok or dataset_ok:
                    results["pins"].append(pin)
                else:
                    results["failed"] += 1

            elif target_type == "board":
                print(f"\n📋 Downloading board: {s} (limit: {limit})")
                board_pins = fetch_board_pins(
                    ctx,
                    s,
                    limit=limit,
                    include_videos=include_videos,
                    skip_ids=ds.ids if ds else None,
                )
                print(f"  Found {len(board_pins)} candidate pins from board")
                for pin in board_pins:
                    results["total_attempted"] += 1
                    folder_ok = False
                    if output_dir:
                        p = save_pin_to_folder(
                            ctx,
                            pin,
                            output_dir,
                            save_meta=save_meta,
                            industry=industry,
                            classifier_mode=classifier_mode,
                        )
                        if p:
                            results["saved_folder"] += 1
                            folder_ok = True

                    dataset_ok = False
                    if ds:
                        if save_pin_to_dataset(
                            ctx,
                            ds,
                            pin,
                            industry=industry,
                            classifier_mode=classifier_mode,
                            min_side=min_side,
                            include_promoted=include_promoted,
                        ):
                            results["saved_dataset"] += 1
                            dataset_ok = True
                        ds.write_stats()

                    if folder_ok or dataset_ok:
                        results["pins"].append(pin)
                    else:
                        results["failed"] += 1

            else:
                # Fallback to search query
                print(f"\n🔎 Searching pins for: {s}")
                pins = search_pins(
                    ctx,
                    s,
                    limit=limit,
                    include_videos=include_videos,
                    skip_ids=ds.ids if ds else None,
                )
                print(f"  Found {len(pins)} candidate pins")
                for pin in pins:
                    results["total_attempted"] += 1
                    folder_ok = False
                    if output_dir:
                        p = save_pin_to_folder(
                            ctx,
                            pin,
                            output_dir,
                            save_meta=save_meta,
                            industry=industry,
                            classifier_mode=classifier_mode,
                        )
                        if p:
                            results["saved_folder"] += 1
                            folder_ok = True

                    dataset_ok = False
                    if ds:
                        if save_pin_to_dataset(
                            ctx,
                            ds,
                            pin,
                            industry=industry,
                            classifier_mode=classifier_mode,
                            min_side=min_side,
                            include_promoted=include_promoted,
                        ):
                            results["saved_dataset"] += 1
                            dataset_ok = True
                        ds.write_stats()

                    if folder_ok or dataset_ok:
                        results["pins"].append(pin)
                    else:
                        results["failed"] += 1

    if ds:
        ds.write_stats()
        if results["saved_dataset"] > 0 and not no_push:
            git_sync.commit_and_push(f"Downloaded {results['saved_dataset']} pins via download tool")

    return results


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Download Pinterest pins by URL, ID, or Board into a folder or dataset.")
    ap.add_argument("targets", nargs="*", help="Pinterest pin URLs, IDs, board URLs, or search keywords")
    ap.add_argument("--file", "-f", type=Path, help="Text file with one URL/ID per line")
    ap.add_argument("-o", "--output", type=Path, help="Target local directory to save images and metadata")
    ap.add_argument("--also-dataset", action="store_true", help="Also save into dataset when --output is provided")
    ap.add_argument("--industry", help="Force specific industry slug (e.g. fintech-finance)")
    ap.add_argument("--classifier", choices=["keywords", "gemini"], help="Override classifier mode")
    ap.add_argument("--limit", type=int, default=50, help="Max pins for board or search download (default 50)")
    ap.add_argument("--min-side", type=int, default=400, help="Skip images smaller than this in px")
    ap.add_argument("--no-meta", action="store_true", help="Don't write .json and .txt metadata when using --output")
    ap.add_argument("--include-videos", action="store_true", help="Include video pins")
    ap.add_argument("--include-promoted", action="store_true", help="Include promoted pins")
    ap.add_argument("--headless", action="store_true", help="Hide browser window")
    ap.add_argument("--no-push", action="store_true", help="Save locally in dataset repo without committing/pushing")
    args = ap.parse_args(argv)

    targets = list(args.targets)
    if args.file:
        targets += [
            l.strip()
            for l in args.file.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")
        ]

    if not targets:
        ap.error("Provide at least one pin URL, pin ID, board URL, or --file")

    output_dir = args.output
    save_to_dataset = True if not output_dir else args.also_dataset

    try:
        res = download_targets(
            targets=targets,
            output_dir=output_dir,
            save_to_dataset=save_to_dataset,
            industry=args.industry,
            classifier_mode=args.classifier,
            limit=args.limit,
            min_side=args.min_side,
            save_meta=not args.no_meta,
            include_videos=args.include_videos,
            include_promoted=args.include_promoted,
            headless=True if args.headless else None,
            no_push=args.no_push,
        )
        print("\n🎉 Download summary:")
        if output_dir:
            print(f"  📁 Saved to folder {output_dir}: {res['saved_folder']} pins")
        if save_to_dataset:
            print(f"  📦 Saved to dataset: {res['saved_dataset']} pins")
        if res["failed"]:
            print(f"  ⚠️ Failed or skipped: {res['failed']}")
    except NotLoggedIn as e:
        sys.exit(f"❌ {e}")
    except Exception as e:
        sys.exit(f"❌ Download error: {e}")


if __name__ == "__main__":
    main()
