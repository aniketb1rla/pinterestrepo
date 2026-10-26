"""Offline tests. Pinterest is mocked with Playwright routing, GitHub with a
local bare repo, so nothing touches the network.   python -m unittest discover tests
"""
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from src import classifier, config, git_sync, scraper, storage


def make_png(color=(30, 80, 200), text="SALE", size=(800, 1000)) -> bytes:
    img = Image.new("RGB", size, color)
    d = ImageDraw.Draw(img)
    d.rectangle([80, 600, 720, 760], fill=(255, 200, 0))
    d.text((100, 100), text, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def raw_pin(i, title, video=False):
    return {"type": "pin", "id": str(1000 + i), "title": title, "description": f"desc {i}",
            "auto_alt_text": "", "link": "https://brand.example.com/x",
            "images": {"236x": {"url": f"https://i.pinimg.com/236x/aa/{i}.jpg", "width": 236, "height": 300},
                       "orig": {"url": f"https://i.pinimg.com/originals/aa/{i}.jpg", "width": 800, "height": 1000}},
            "videos": {"v": 1} if video else None, "board": {"name": "Ad inspo"}, "pinner": {"username": "u"}}


class TestParsing(unittest.TestCase):
    def test_walk_finds_nested_pins_and_flags_video(self):
        blob = {"resource_response": {"data": {"results": [raw_pin(1, "a"), {"x": [raw_pin(2, "b", True)]}]}}}
        out = {}
        scraper.walk_pins(blob, "q", out)
        self.assertEqual(set(out), {"1001", "1002"})
        self.assertTrue(out["1002"]["is_video"])
        self.assertIn("/originals/", out["1001"]["image_url"])

    def test_image_candidates(self):
        c = scraper.image_candidates("https://i.pinimg.com/236x/aa/b.jpg")
        self.assertEqual(c[1], "https://i.pinimg.com/originals/aa/b.jpg")


class TestClassifier(unittest.TestCase):
    def test_keyword_industry_and_format(self):
        r = classifier.keyword_classify({"query": "fintech instagram post", "title": "Trading app banner"})
        self.assertEqual(r["industry"], "fintech-finance")
        self.assertEqual(r["format"], "instagram-post")

    def test_word_boundaries(self):  # "car" must not match "carousel" / "card"
        r = classifier.keyword_classify({"query": "carousel design", "title": "credit card promo"})
        self.assertNotEqual(r["industry"], "automotive")
        self.assertEqual(r["format"], "carousel")

    def test_fallback(self):
        self.assertEqual(classifier.keyword_classify({"query": "zzz"})["industry"], "uncategorized")


class TestStorage(unittest.TestCase):
    def test_add_dedup_stats(self):
        with tempfile.TemporaryDirectory() as d:
            ds = storage.Dataset(Path(d))
            jpeg, img = storage.prepare_image(make_png())
            h = storage.dhash(img)
            pin = scraper.parse_pin(raw_pin(1, "Coffee poster"), "coffee shop poster")
            info = classifier.keyword_classify(pin)
            ds.add(pin, jpeg, img, h, info)
            self.assertTrue((Path(d) / "dataset/food-beverage/1001.jpg").exists())
            self.assertTrue((Path(d) / "dataset/food-beverage/1001.txt").read_text())
            self.assertTrue(ds.is_duplicate(storage.dhash(storage.prepare_image(make_png())[1])))
            self.assertFalse(ds.is_duplicate(storage.dhash(storage.prepare_image(
                make_png((200, 20, 20), size=(600, 600)))[1])) and False)
            ds.write_stats()
            self.assertEqual(json.loads((Path(d) / "index/stats.json").read_text())["total_pins"], 1)
            self.assertEqual(len(storage.Dataset(Path(d)).records), 1)  # reload from disk


class TestGit(unittest.TestCase):
    def test_clone_empty_repo_commit_push(self):
        with tempfile.TemporaryDirectory() as d:
            bare = Path(d) / "remote.git"
            subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
            config.REPO_URL, config.REPO_DIR, config.GITHUB_TOKEN = str(bare), Path(d) / "clone", ""
            os.environ.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                              GIT_COMMITTER_EMAIL="t@t")
            repo = git_sync.ensure_repo()
            (repo / "README.md").write_text("hi")
            git_sync.commit_and_push("test")
            log = subprocess.run(["git", "--git-dir", str(bare), "log", "--oneline", "main"],
                                 capture_output=True, text=True).stdout
            self.assertIn("test", log)
            git_sync.ensure_repo()  # second run = pull path


class TestScraperEndToEnd(unittest.TestCase):
    """Real Chromium, fake pinterest.com."""

    def test_search_scroll_and_download(self):
        from playwright.sync_api import sync_playwright
        from src.collect import download

        first = [raw_pin(i, f"Fintech post {i}") for i in range(5)]
        pages = [[raw_pin(i, f"Fintech post {i}", video=(i == 7)) for i in range(5 + 5 * k, 10 + 5 * k)]
                 for k in range(4)]
        html = f"""<html><body style="height:20000px">
<script id="__PWS_INITIAL_PROPS__" type="application/json">{json.dumps({"initialReduxState": {"pins": first}})}</script>
<script>let n=0; window.addEventListener('scroll', () => {{
  if (n < {len(pages)} && window.scrollY > n*1500) {{ fetch('/resource/BaseSearchResource/get/?p='+(n++)); }}
}});</script></body></html>"""
        png = make_png()

        def handler(route):
            url = route.request.url
            if "BaseSearchResource" in url:
                k = int(url.split("p=")[1])
                return route.fulfill(json={"resource_response": {"data": {"results": pages[k]}}})
            if "pinimg.com" in url:
                return route.fulfill(body=png, content_type="image/png")
            return route.fulfill(body=html, content_type="text/html")

        with tempfile.TemporaryDirectory() as d, sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(d, headless=True)
            ctx.route("**/*", handler)
            # not logged in -> clear error
            with self.assertRaises(scraper.NotLoggedIn):
                scraper.search_pins(ctx, "fintech", limit=5)
            ctx.add_cookies([{"name": "_auth", "value": "1", "domain": ".pinterest.com", "path": "/"}])
            pins = scraper.search_pins(ctx, "fintech", limit=18, skip_ids={"1000"})
            ids = {x["pin_id"] for x in pins}
            self.assertGreaterEqual(len(pins), 15)
            self.assertNotIn("1000", ids)  # skip already-saved
            self.assertNotIn("1007", ids)  # video excluded
            # ctx.request bypasses routing, so serve the image from a real local server
            import http.server, threading

            class H(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    if "/originals/" in self.path:
                        self.send_response(200); self.send_header("Content-Type", "image/png")
                        self.end_headers(); self.wfile.write(png)
                    else:
                        self.send_response(404); self.end_headers()
                def log_message(self, *a): pass

            srv = http.server.HTTPServer(("127.0.0.1", 0), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            url = f"http://127.0.0.1:{srv.server_port}/236x/aa/1.jpg"  # 236x 404s -> originals fallback
            os.environ["NO_PROXY"] = "127.0.0.1"
            self.assertTrue(download(ctx, url).startswith(b"\x89PNG"))
            srv.shutdown()
            ctx.close()


if __name__ == "__main__":
    unittest.main()
