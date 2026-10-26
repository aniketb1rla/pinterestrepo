"""Unit tests for the local web server and gallery API."""
import io
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from src import server


class TestServer(unittest.TestCase):
    def setUp(self):
        os.environ["NO_PROXY"] = "127.0.0.1,localhost"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "index").mkdir(parents=True)
        (self.root / "dataset" / "fintech-finance").mkdir(parents=True)

        # Write sample pin file and image
        sample_pin = {
            "pin_id": "999001",
            "pin_url": "https://www.pinterest.com/pin/999001/",
            "image_url": "https://i.pinimg.com/orig/999001.jpg",
            "title": "Fintech Mobile App UI Design",
            "description": "Clean finance tracker dashboard",
            "alt_text": "mockup of fintech mobile screen",
            "query": "fintech app ui",
            "industry": "fintech-finance",
            "format": "instagram-post",
            "caption": "A clean blue modern finance app interface for tracking investments.",
            "palette": ["#0055ff", "#ffffff"],
            "image_path": "dataset/fintech-finance/999001.jpg",
            "caption_path": "dataset/fintech-finance/999001.txt",
            "collected_at": "2026-10-22T08:00:00+00:00",
            "created_at": "2026-10-20T10:00:00+00:00",
        }
        sample_pin2 = {
            "pin_id": "999002",
            "pin_url": "https://www.pinterest.com/pin/999002/",
            "image_url": "https://i.pinimg.com/orig/999002.jpg",
            "title": "Organic Skincare Serum Ad",
            "description": "Minimalist beauty cosmetics poster",
            "alt_text": "skincare bottle on stone",
            "query": "skincare ad design",
            "industry": "beauty-cosmetics",
            "format": "ad-creative",
            "caption": "Glass dropper bottle on neutral stone backdrop.",
            "palette": ["#e0d8c0", "#302820"],
            "image_path": "dataset/beauty-cosmetics/999002.jpg",
            "caption_path": "dataset/beauty-cosmetics/999002.txt",
            "collected_at": "2026-10-22T09:00:00+00:00",
            "created_at": "2026-10-21T10:00:00+00:00",
        }

        with open(self.root / "index" / "pins.jsonl", "w", encoding="utf-8") as f:
            f.write(json.dumps(sample_pin) + "\n")
            f.write(json.dumps(sample_pin2) + "\n")

        # Fake image file
        (self.root / "dataset" / "fintech-finance" / "999001.jpg").write_bytes(b"\xff\xd8\xff\xe0testjpeg")

        # Initialize test server
        self.httpd, self.port = server.create_server(host="127.0.0.1", port=0, repo_dir=self.root)
        import threading
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.temp_dir.cleanup()

    def test_store_stats_and_filtering(self):
        store = server.ReferenceStore(self.root)
        stats = store.get_stats()
        self.assertEqual(stats["total_pins"], 2)
        self.assertEqual(stats["by_industry"]["fintech-finance"], 1)
        self.assertEqual(stats["by_industry"]["beauty-cosmetics"], 1)

        # Filter by industry
        filtered = store.filter_pins(industry="fintech-finance")
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["pins"][0]["pin_id"], "999001")

        # Search query
        searched = store.filter_pins(query="serum")
        self.assertEqual(searched["total"], 1)
        self.assertEqual(searched["pins"][0]["pin_id"], "999002")

        # Sort: latest first (999002 collected at 09:00 should be first)
        sorted_latest = store.filter_pins(sort="latest")
        self.assertEqual(sorted_latest["pins"][0]["pin_id"], "999002")

        # Sort: oldest first (999001 collected at 08:00 should be first)
        sorted_oldest = store.filter_pins(sort="oldest")
        self.assertEqual(sorted_oldest["pins"][0]["pin_id"], "999001")

        # Sort: title_asc ("Fintech..." before "Organic...")
        sorted_title = store.filter_pins(sort="title_asc")
        self.assertEqual(sorted_title["pins"][0]["pin_id"], "999001")
        self.assertEqual(sorted_title["pins"][1]["pin_id"], "999002")

        # Sort: title_desc ("Organic..." before "Fintech...")
        sorted_title_desc = store.filter_pins(sort="title_desc")
        self.assertEqual(sorted_title_desc["pins"][0]["pin_id"], "999002")

    def test_http_api_endpoints(self):
        base_url = f"http://127.0.0.1:{self.port}"

        # 1. /api/stats
        req = urllib.request.urlopen(f"{base_url}/api/stats")
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertEqual(data["total_pins"], 2)

        # 2. /api/pins
        req = urllib.request.urlopen(f"{base_url}/api/pins?industry=beauty-cosmetics")
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["pins"][0]["pin_id"], "999002")

        # 3. /dataset/fintech-finance/999001.jpg
        req = urllib.request.urlopen(f"{base_url}/dataset/fintech-finance/999001.jpg")
        self.assertEqual(req.status, 200)
        content = req.read()
        self.assertTrue(content.startswith(b"\xff\xd8"))

        # 4. Traversal protection
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{base_url}/dataset/../../index/pins.jsonl")
        self.assertIn(ctx.exception.code, (403, 404))

        # 5. Root page
        req = urllib.request.urlopen(f"{base_url}/")
        self.assertEqual(req.status, 200)
        html_content = req.read().decode("utf-8")
        self.assertIn("Pinterest Reference Gallery", html_content)

        # 6. /api/collect/status
        req = urllib.request.urlopen(f"{base_url}/api/collect/status")
        self.assertEqual(req.status, 200)
        status_data = json.loads(req.read().decode("utf-8"))
        self.assertIn("active", status_data)

        # 7. POST /api/collect invalid query
        post_req = urllib.request.Request(
            f"{base_url}/api/collect",
            data=json.dumps({"query": ""}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(post_req)
        self.assertEqual(ctx.exception.code, 400)

        # 8. GET /api/export-pin format=zip
        req = urllib.request.urlopen(f"{base_url}/api/export-pin?pin_id=999001&format=zip")
        self.assertEqual(req.status, 200)
        self.assertEqual(req.headers.get("Content-Type"), "application/zip")
        import zipfile
        with zipfile.ZipFile(io.BytesIO(req.read())) as zf:
            names = zf.namelist()
            self.assertIn("999001.jpg", names)
            self.assertIn("999001.txt", names)
            self.assertIn("999001.json", names)

        # 9. POST /api/export-batch
        batch_req = urllib.request.Request(
            f"{base_url}/api/export-batch",
            data=json.dumps({"pin_ids": ["999001", "999002"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        req = urllib.request.urlopen(batch_req)
        self.assertEqual(req.status, 200)
        self.assertEqual(req.headers.get("Content-Type"), "application/zip")
        with zipfile.ZipFile(io.BytesIO(req.read())) as zf:
            self.assertIn("index.json", zf.namelist())
            self.assertIn("fintech-finance/999001.jpg", zf.namelist())

        # 10. POST /api/download empty target validation
        dl_req = urllib.request.Request(
            f"{base_url}/api/download",
            data=json.dumps({"targets": []}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(dl_req)
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
