"""Re-sort / re-caption pins already in the dataset (e.g. after editing
categories.yaml, or to upgrade keyword captions to Gemini ones).

  python -m src.reclassify --classifier gemini
  python -m src.reclassify --only-uncategorized
"""
import argparse
import json
import shutil

from . import config, git_sync
from .classifier import classify
from .storage import INDEX, Dataset


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--classifier", choices=["keywords", "gemini"])
    ap.add_argument("--only-uncategorized", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args(argv)

    if not args.no_push:
        git_sync.ensure_repo()
    root = config.REPO_DIR
    ds = Dataset(root)
    changed = 0
    for rec in ds.records:
        if args.only_uncategorized and rec["industry"] != "uncategorized":
            continue
        img_path = root / rec["image_path"]
        if not img_path.exists():
            continue
        info = classify(rec, img_path.read_bytes(), mode=args.classifier)
        old = rec["industry"]
        rec.update(info)
        if info["industry"] != old:
            new_dir = root / "dataset" / info["industry"]
            new_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(img_path), new_dir / img_path.name)
            old_txt = root / rec["caption_path"]
            if old_txt.exists():
                old_txt.unlink()
            rec["image_path"] = f"dataset/{info['industry']}/{img_path.name}"
            rec["caption_path"] = f"dataset/{info['industry']}/{rec['pin_id']}.txt"
        (root / rec["caption_path"]).write_text(info.get("caption") or "", encoding="utf-8")
        changed += 1
        print(f"  {rec['pin_id']}: {old} → {info['industry']}")

    # rebuild jsonl files from the updated records
    for f in (root / "dataset").glob("*/metadata.jsonl"):
        f.unlink()
    lines = []
    for rec in ds.records:
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        lines.append(line)
        with open(root / "dataset" / rec["industry"] / "metadata.jsonl", "a", encoding="utf-8") as f:
            f.write(line)
    (root / INDEX).write_text("".join(lines), encoding="utf-8")
    for d in (root / "dataset").iterdir():  # drop empty folders
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    ds.write_stats()
    print(f"Reclassified {changed} pins.")
    if changed and not args.no_push:
        git_sync.commit_and_push(f"Reclassify {changed} pins")


if __name__ == "__main__":
    main()
