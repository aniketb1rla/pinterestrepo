"""Writes pins into the dataset repo in a training-friendly layout.

pinterestrepo/
  README.md                      auto-updated stats
  dataset/<industry>/<pin_id>.jpg
  dataset/<industry>/<pin_id>.txt  training caption (LoRA / kohya style)
  dataset/<industry>/metadata.jsonl
  index/pins.jsonl               every pin, all fields (master database)
  index/stats.json
"""
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from . import config
from .classifier import load_categories

INDEX = "index/pins.jsonl"


# ---------- image helpers ----------------------------------------------------
def dhash(img: Image.Image, size: int = 8) -> str:
    g = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(g.get_flattened_data() if hasattr(g, "get_flattened_data") else g.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (left > right)
    return f"{bits:016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def palette(img: Image.Image, n: int = 5) -> list[str]:
    small = img.convert("RGB").copy()
    small.thumbnail((150, 150))
    q = small.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    return ["#{:02x}{:02x}{:02x}".format(*pal[i * 3:i * 3 + 3]) for _, i in counts[:n]]


def prepare_image(raw: bytes) -> tuple[bytes, Image.Image]:
    img = Image.open(io.BytesIO(raw))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")
    img.thumbnail((config.MAX_IMAGE_SIDE, config.MAX_IMAGE_SIDE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=config.JPEG_QUALITY, optimize=True, progressive=True)
    return buf.getvalue(), img


# ---------- dataset ----------------------------------------------------------
class Dataset:
    def __init__(self, root: Path):
        self.root = root
        (root / "index").mkdir(parents=True, exist_ok=True)
        (root / "dataset").mkdir(parents=True, exist_ok=True)
        self.records: list[dict] = []
        idx = root / INDEX
        if idx.exists():
            with idx.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self.records.append(json.loads(line))
        self.ids = {r["pin_id"] for r in self.records}
        self.hashes = [r["dhash"] for r in self.records if r.get("dhash")]

    def is_duplicate(self, h: str) -> bool:
        return any(hamming(h, x) <= config.DUPLICATE_HAMMING for x in self.hashes)

    def add(self, pin: dict, jpeg: bytes, img: Image.Image, h: str, info: dict) -> dict:
        industry = info["industry"]
        folder = self.root / "dataset" / industry
        folder.mkdir(parents=True, exist_ok=True)
        rel_img = f"dataset/{industry}/{pin['pin_id']}.jpg"
        (self.root / rel_img).write_bytes(jpeg)
        (folder / f"{pin['pin_id']}.txt").write_text(info.get("caption") or "", encoding="utf-8")

        record = {
            **{k: v for k, v in pin.items() if not k.startswith("_")},
            **info,
            "image_path": rel_img,
            "caption_path": f"dataset/{industry}/{pin['pin_id']}.txt",
            "saved_width": img.width,
            "saved_height": img.height,
            "aspect_ratio": round(img.width / img.height, 3),
            "palette": palette(img),
            "dhash": h,
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with open(folder / "metadata.jsonl", "a", encoding="utf-8") as f:
            f.write(line)
        with open(self.root / INDEX, "a", encoding="utf-8") as f:
            f.write(line)
        self.records.append(record)
        self.ids.add(pin["pin_id"])
        self.hashes.append(h)
        return record

    def write_stats(self) -> None:
        labels = {k: v["label"] for k, v in load_categories()["industries"].items()}
        by_ind = Counter(r["industry"] for r in self.records)
        by_fmt = Counter(r.get("format") or "unknown" for r in self.records)
        queries = Counter(r.get("query") for r in self.records)
        stats = {
            "total_pins": len(self.records),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "by_industry": dict(by_ind.most_common()),
            "industry_labels": labels,
            "by_format": dict(by_fmt.most_common()),
            "queries": dict(queries.most_common()),
        }
        (self.root / "index" / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

        rows = "\n".join(f"| `{k}` | {labels.get(k, k)} | {v} |" for k, v in by_ind.most_common())
        fmt_rows = "\n".join(f"| {k} | {v} |" for k, v in by_fmt.most_common())
        dataset_doc = f"""# Design Reference Dataset

Graphic-design references (ads & social posts) collected from Pinterest and
sorted by industry, for training / prompting AI design models.

**{len(self.records)} pins** · last updated {stats['updated_at'][:10]}

## By industry
| Folder | Industry | Pins |
|---|---|---|
{rows}

## By format
| Format | Pins |
|---|---|
{fmt_rows}

## Layout
```
dataset/<industry>/<pin_id>.jpg       image (max {config.MAX_IMAGE_SIDE}px)
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
"""
        (self.root / "DATASET.md").write_text(dataset_doc, encoding="utf-8")
        readme_path = self.root / "README.md"
        if readme_path.exists():
            existing = readme_path.read_text(encoding="utf-8")
            if "## Current Dataset Statistics" in existing:
                top = existing.split("## Current Dataset Statistics")[0]
                readme_path.write_text(f"{top}## Current Dataset Statistics\n\n**{len(self.records)} pins** · last updated {stats['updated_at'][:10]}\n\n### By industry\n| Folder | Industry | Pins |\n|---|---|---|\n{rows}\n\n### By format\n| Format | Pins |\n|---|---|\n{fmt_rows}\n", encoding="utf-8")
            elif "Pinterest Reference Collector" not in existing:
                readme_path.write_text(dataset_doc, encoding="utf-8")
        else:
            readme_path.write_text(dataset_doc, encoding="utf-8")
