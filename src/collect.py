"""Main command.

  python -m src.collect "fintech instagram post" --limit 60
  python -m src.collect "coffee ad" "burger poster" --limit 40 --classifier gemini
  python -m src.collect --file keywords.txt --limit 30
  python -m src.collect "real estate flyer" --industry real-estate --no-push
"""
import argparse
import sys
from pathlib import Path

from . import config, git_sync
from .browser import open_context
from .classifier import classify, load_categories
from .scraper import NotLoggedIn, fetch_board_pins, fetch_pin, image_candidates, parse_target, search_pins
from .storage import Dataset, dhash, prepare_image


def download(ctx, url: str) -> bytes | None:
    for u in image_candidates(url):
        try:
            r = ctx.request.get(u, timeout=30000, headers={"Referer": "https://www.pinterest.com/"})
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                return r.body()
        except Exception:
            pass
    return None


def save_pin_to_dataset(ctx, ds: Dataset, pin: dict, args) -> bool:
    if not args.include_promoted and pin.get("is_promoted"):
        return False
    raw = download(ctx, pin["image_url"])
    if not raw:
        print(f"  [{pin.get('pin_id', 'pin')}] download failed")
        return False
    try:
        jpeg, img = prepare_image(raw)
    except Exception:
        return False
    if min(img.size) < args.min_side:
        return False
    h = dhash(img)
    if ds.is_duplicate(h):
        print(f"  [{pin.get('pin_id', 'pin')}] duplicate — skipped")
        return False
    info = classify(pin, jpeg, force_industry=args.industry, mode=args.classifier)
    if config.DROP_NON_DESIGN and info.get("is_design") is False:
        print(f"  [{pin.get('pin_id', 'pin')}] plain photo — skipped")
        return False
    ds.add(pin, jpeg, img, h, info)
    print(f"  ✓ {info['industry']:<22} {(pin.get('title') or pin.get('alt_text') or pin.get('pin_id'))[:60]}")
    return True


def run_query(ctx, ds: Dataset, query: str, args) -> int:
    print(f"\n🔎 {query}")
    pins = search_pins(ctx, query, limit=args.limit, include_videos=args.include_videos, skip_ids=ds.ids)
    print(f"  {len(pins)} new candidate pins")
    saved = 0
    for pin in pins:
        if save_pin_to_dataset(ctx, ds, pin, args):
            saved += 1
    return saved


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Collect Pinterest design references into your GitHub dataset repo.")
    ap.add_argument("keywords", nargs="*", help="search keywords (quote multi-word ones)")
    ap.add_argument("--file", type=Path, help="text file with one keyword per line")
    ap.add_argument("--limit", type=int, default=50, help="pins per keyword (default 50)")
    ap.add_argument("--industry", help="force all pins into this industry slug")
    ap.add_argument("--classifier", choices=["keywords", "gemini"], help="override CLASSIFIER in .env")
    ap.add_argument("--min-side", type=int, default=400, help="skip images smaller than this (px)")
    ap.add_argument("--include-videos", action="store_true")
    ap.add_argument("--include-promoted", action="store_true")
    ap.add_argument("--headless", action="store_true", help="hide the browser window")
    ap.add_argument("--no-push", action="store_true", help="save locally, don't commit/push")
    args = ap.parse_args(argv)

    keywords = list(args.keywords)
    if args.file:
        keywords += [l.strip() for l in args.file.read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith("#")]
    if not keywords:
        ap.error("give at least one keyword or --file")
    if args.industry and args.industry not in load_categories()["industries"]:
        ap.error(f"unknown industry '{args.industry}'. See config/categories.yaml")

    repo = git_sync.ensure_repo() if not args.no_push else config.REPO_DIR
    ds = Dataset(repo)
    total = 0
    try:
        with open_context(headless=True if args.headless else None) as ctx:
            for q in keywords:
                parsed = parse_target(q)
                target_type = parsed["type"]
                if target_type in ("pin", "pin_short"):
                    print(f"\n📌 Pin: {q}")
                    pin = fetch_pin(ctx, q)
                    if pin and save_pin_to_dataset(ctx, ds, pin, args):
                        total += 1
                elif target_type == "board":
                    print(f"\n📋 Board: {q} (limit: {args.limit})")
                    board_pins = fetch_board_pins(
                        ctx,
                        q,
                        limit=args.limit,
                        include_videos=args.include_videos,
                        skip_ids=ds.ids,
                    )
                    for pin in board_pins:
                        if save_pin_to_dataset(ctx, ds, pin, args):
                            total += 1
                else:
                    total += run_query(ctx, ds, q, args)
                ds.write_stats()
    except NotLoggedIn as e:
        sys.exit(f"❌ {e}")
    finally:
        ds.write_stats()

    print(f"\n📦 Saved {total} new pins · dataset total {len(ds.records)}")
    if total and not args.no_push:
        git_sync.commit_and_push(f"Add {total} pins: {', '.join(keywords)[:120]}")


if __name__ == "__main__":
    main()
