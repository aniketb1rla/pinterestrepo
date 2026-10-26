"""Searches Pinterest and harvests pin data.

Primary source: the JSON Pinterest's own web app loads while you scroll
(BaseSearchResource). Fallback: the pin cards visible in the page.
"""
import json
import random
import re
from urllib.parse import quote_plus, urlparse

from playwright.sync_api import BrowserContext, Page

from . import config
from .browser import get_page, is_logged_in

_SIZE_RE = re.compile(r"/(\d+x\d*|originals)/")


class NotLoggedIn(RuntimeError):
    pass


def _best_image(images: dict) -> tuple[str, int, int] | None:
    if not isinstance(images, dict) or not images:
        return None
    if "orig" in images and images["orig"].get("url"):
        o = images["orig"]
        return o["url"], o.get("width", 0), o.get("height", 0)
    best = max(images.values(), key=lambda v: (v or {}).get("width", 0) or 0)
    return (best["url"], best.get("width", 0), best.get("height", 0)) if best and best.get("url") else None


def image_candidates(url: str) -> list[str]:
    """originals first (full res), then 736x as a safe fallback."""
    out = [url]
    if _SIZE_RE.search(url):
        for size in ("originals", "736x"):
            u = _SIZE_RE.sub(f"/{size}/", url, count=1)
            if u not in out:
                out.append(u)
    return out


def parse_pin(raw: dict, query: str) -> dict | None:
    if not isinstance(raw, dict) or raw.get("type") != "pin" or not raw.get("id"):
        return None
    img = _best_image(raw.get("images"))
    if not img:
        return None
    is_video = bool(raw.get("videos") or raw.get("is_video")
                    or (raw.get("story_pin_data") or {}).get("has_video"))
    link = raw.get("link") or ""
    pinner = raw.get("pinner") or {}
    board = raw.get("board") or {}
    return {
        "pin_id": str(raw["id"]),
        "pin_url": f"https://www.pinterest.com/pin/{raw['id']}/",
        "image_url": img[0],
        "width": img[1],
        "height": img[2],
        "title": (raw.get("title") or raw.get("grid_title") or "").strip(),
        "description": (raw.get("description") or "").strip(),
        "alt_text": (raw.get("auto_alt_text") or raw.get("seo_alt_text") or "").strip(),
        "dominant_color": raw.get("dominant_color"),
        "source_link": link,
        "source_domain": urlparse(link).netloc if link else (raw.get("domain") or ""),
        "pinner": pinner.get("username") if isinstance(pinner, dict) else None,
        "board": board.get("name") if isinstance(board, dict) else None,
        "is_video": is_video,
        "is_promoted": bool(raw.get("is_promoted")),
        "created_at": raw.get("created_at"),
        "query": query,
    }


def walk_pins(obj, query: str, out: dict) -> None:
    """Recursively find pin objects anywhere in a JSON blob."""
    if isinstance(obj, dict):
        pin = parse_pin(obj, query)
        if pin:
            out.setdefault(pin["pin_id"], pin)
            return
        for v in obj.values():
            walk_pins(v, query, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_pins(v, query, out)


_DOM_JS = """
() => Array.from(document.querySelectorAll('a[href*="/pin/"]')).map(a => {
  const img = a.querySelector('img');
  const m = a.getAttribute('href').match(/\\/pin\\/([\\w-]+)/);
  if (!img || !m) return null;
  let src = img.currentSrc || img.src || '';
  const ss = img.getAttribute('srcset');
  if (ss) { const parts = ss.split(',').map(s => s.trim().split(' ')[0]); src = parts[parts.length-1] || src; }
  return {id: m[1], src, alt: img.alt || ''};
}).filter(Boolean)
"""

_PIN_PAGE_DOM_JS = """
() => {
  const meta = (name) => {
    const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
    return el ? el.getAttribute('content') : '';
  };
  let imgUrl = meta('og:image');
  if (!imgUrl) {
    const img = document.querySelector('[data-test-id="pin-closeup-image"] img, [data-test-id="pin-image"] img, div[data-test-id*="visual"] img, main img[src*="pinimg.com"]');
    if (img) imgUrl = img.currentSrc || img.src || '';
  }
  const title = meta('og:title') || document.querySelector('h1')?.innerText || '';
  const desc = meta('og:description') || document.querySelector('[data-test-id="pin-description"], [data-test-id="truncated-description"]')?.innerText || '';
  const canonical = meta('og:url') || window.location.href;
  return {
    image_url: imgUrl,
    title: (title || '').trim(),
    description: (desc || '').trim(),
    url: canonical
  };
}
"""


def parse_target(target: str) -> dict:
    """Identify if target is a Pin ID, Pin URL, short link, Board URL, or keyword query."""
    s = target.strip()
    if not s:
        return {"type": "empty", "raw": s}

    # Pin ID directly (e.g. 112590053177724123)
    if re.fullmatch(r"\d{6,25}", s):
        return {
            "type": "pin",
            "pin_id": s,
            "url": f"https://www.pinterest.com/pin/{s}/",
            "raw": s,
        }

    # pin.it short links
    if "pin.it/" in s:
        url = s if s.startswith("http://") or s.startswith("https://") else f"https://{s}"
        return {
            "type": "pin_short",
            "pin_id": None,
            "url": url,
            "raw": s,
        }

    # Specific pin URL: pinterest.com/pin/123456789/ or with title-slug--123456789/
    pin_match = re.search(r"pinterest\.[a-z.]+/pin/(?:[\w-]+--|[\w-]+-)?(\d+)", s)
    if pin_match:
        pid = pin_match.group(1)
        url = s if s.startswith("http://") or s.startswith("https://") else f"https://{s}"
        return {
            "type": "pin",
            "pin_id": pid,
            "url": url,
            "raw": s,
        }

    # Board URL: pinterest.com/username/boardname/
    board_match = re.search(r"pinterest\.[a-z.]+/([^/?#]+)/([^/?#]+)/?", s)
    if board_match:
        user = board_match.group(1)
        board = board_match.group(2)
        reserved = ("pin", "search", "ideas", "today", "settings", "business", "resource")
        if user not in reserved and board not in ("sent", "feedback", "activity", "boards"):
            url = s if s.startswith("http://") or s.startswith("https://") else f"https://{s}"
            return {
                "type": "board",
                "username": user,
                "board_slug": board,
                "url": url,
                "raw": s,
            }

    return {
        "type": "query",
        "query": s,
        "raw": s,
    }


def _harvest_dom(page: Page, query: str, out: dict) -> None:
    try:
        cards = page.evaluate(_DOM_JS)
    except Exception:
        return
    for c in cards:
        if c["id"] in out or "pinimg.com" not in c["src"]:
            continue
        out[c["id"]] = {
            "pin_id": c["id"], "pin_url": f"https://www.pinterest.com/pin/{c['id']}/",
            "image_url": c["src"], "width": 0, "height": 0, "title": "", "description": "",
            "alt_text": c["alt"], "dominant_color": None, "source_link": "", "source_domain": "",
            "pinner": None, "board": None, "is_video": False, "is_promoted": False,
            "created_at": None, "query": query, "_from_dom": True,
        }


def fetch_pin(ctx: BrowserContext, target: str) -> dict | None:
    """Fetch complete pin details for a single pin URL or Pin ID."""
    page = get_page(ctx)
    parsed = parse_target(target)
    target_url = parsed.get("url") or target
    found: dict[str, dict] = {}

    def on_response(resp):
        if resp.status != 200:
            return
        if any(k in resp.url for k in ("PinResource", "PinPageResource", "PinActivityResource", "SearchResource", "resource")):
            try:
                walk_pins(resp.json(), "", found)
            except Exception:
                pass

    page.on("response", on_response)
    try:
        page.goto(config.PINTEREST_HOME, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        if not is_logged_in(ctx):
            raise NotLoggedIn("Not logged in to Pinterest. Run:  python -m src.login")

        page.goto(target_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        # Embedded JSON props
        for sel in ("script#__PWS_INITIAL_PROPS__", "script#__PWS_DATA__"):
            try:
                el = page.query_selector(sel)
                if el:
                    walk_pins(json.loads(el.inner_text()), "", found)
            except Exception:
                pass

        # Determine target pin ID if possible
        current_id = parsed.get("pin_id")
        if not current_id:
            m = re.search(r"/pin/(?:[\w-]+--|[\w-]+-)?(\d+)", page.url)
            if m:
                current_id = m.group(1)

        if current_id and current_id in found:
            return found[current_id]

        if found:
            if current_id:
                for k, p in found.items():
                    if k == current_id:
                        return p
            return list(found.values())[0]

        # Fallback to DOM elements
        dom_data = page.evaluate(_PIN_PAGE_DOM_JS)
        if dom_data and dom_data.get("image_url"):
            img_cands = image_candidates(dom_data["image_url"])
            orig_img = img_cands[1] if len(img_cands) > 1 else img_cands[0]
            pid = current_id or str(abs(hash(target_url)))[:12]
            return {
                "pin_id": pid,
                "pin_url": dom_data.get("url") or f"https://www.pinterest.com/pin/{pid}/",
                "image_url": orig_img,
                "width": 0,
                "height": 0,
                "title": dom_data.get("title") or "",
                "description": dom_data.get("description") or "",
                "alt_text": dom_data.get("title") or "",
                "dominant_color": None,
                "source_link": dom_data.get("url") or "",
                "source_domain": urlparse(dom_data.get("url") or "").netloc,
                "pinner": None,
                "board": None,
                "is_video": False,
                "is_promoted": False,
                "created_at": None,
                "query": "",
                "_from_dom": True,
            }
        return None
    finally:
        page.remove_listener("response", on_response)


def fetch_board_pins(ctx: BrowserContext, board_url_or_target: str, limit: int = 50,
                     include_videos: bool = False, skip_ids: set[str] | None = None) -> list[dict]:
    """Fetch pins from a Pinterest board URL with polite scrolling."""
    skip_ids = skip_ids or set()
    page = get_page(ctx)
    parsed = parse_target(board_url_or_target)
    board_url = parsed.get("url") or board_url_or_target
    found: dict[str, dict] = {}

    def on_response(resp):
        if resp.status != 200:
            return
        if any(k in resp.url for k in ("BoardFeedResource", "BoardResource", "SearchResource", "BaseSearchResource", "Resource")):
            try:
                walk_pins(resp.json(), "board", found)
            except Exception:
                pass

    page.on("response", on_response)
    try:
        page.goto(config.PINTEREST_HOME, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        if not is_logged_in(ctx):
            raise NotLoggedIn("Not logged in to Pinterest. Run:  python -m src.login")

        page.goto(board_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3500)

        for sel in ("script#__PWS_INITIAL_PROPS__", "script#__PWS_DATA__"):
            try:
                el = page.query_selector(sel)
                if el:
                    walk_pins(json.loads(el.inner_text()), "board", found)
            except Exception:
                pass

        def usable() -> list[dict]:
            return [p for p in found.values()
                    if p["pin_id"] not in skip_ids and (include_videos or not p["is_video"])]

        stagnant, scrolls = 0, 0
        while len(usable()) < limit and stagnant < 6 and scrolls < config.MAX_SCROLLS:
            before = len(found)
            _harvest_dom(page, "board", found)
            page.mouse.wheel(0, random.randint(1800, 2600))
            page.wait_for_timeout(random.randint(1300, 2600))  # polite pace
            scrolls += 1
            stagnant = stagnant + 1 if len(found) == before else 0
            print(f"  scrolling board… {len(usable())}/{limit} pins", end="\r")
        print()
        return usable()[:limit]
    finally:
        page.remove_listener("response", on_response)


def search_pins(ctx: BrowserContext, query: str, limit: int = 50,
                include_videos: bool = False, skip_ids: set[str] | None = None) -> list[dict]:
    skip_ids = skip_ids or set()
    page = get_page(ctx)
    found: dict[str, dict] = {}

    def on_response(resp):
        if "SearchResource" not in resp.url or resp.status != 200:
            return
        try:
            walk_pins(resp.json(), query, found)
        except Exception:
            pass

    page.on("response", on_response)
    try:
        page.goto(config.PINTEREST_HOME, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        if not is_logged_in(ctx):
            raise NotLoggedIn("Not logged in to Pinterest. Run:  python -m src.login")

        page.goto(f"{config.PINTEREST_HOME}/search/pins/?q={quote_plus(query)}&rs=typed",
                  wait_until="domcontentloaded")
        page.wait_for_timeout(3500)

        # first screen of results is embedded in the HTML
        for sel in ("script#__PWS_INITIAL_PROPS__", "script#__PWS_DATA__"):
            try:
                el = page.query_selector(sel)
                if el:
                    walk_pins(json.loads(el.inner_text()), query, found)
            except Exception:
                pass

        def usable() -> list[dict]:
            return [p for p in found.values()
                    if p["pin_id"] not in skip_ids and (include_videos or not p["is_video"])]

        stagnant, scrolls = 0, 0
        while len(usable()) < limit and stagnant < 6 and scrolls < config.MAX_SCROLLS:
            before = len(found)
            _harvest_dom(page, query, found)
            page.mouse.wheel(0, random.randint(1800, 2600))
            page.wait_for_timeout(random.randint(1300, 2600))  # human-ish pace
            scrolls += 1
            stagnant = stagnant + 1 if len(found) == before else 0
            print(f"  scrolling… {len(usable())}/{limit} pins", end="\r")
        print()
        return usable()[:limit]
    finally:
        page.remove_listener("response", on_response)
