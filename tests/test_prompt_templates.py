"""Unit tests for design analyzer, prompt generator, and template management APIs."""
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from src import config, design_analyzer, server


class TestPromptTemplates(unittest.TestCase):
    def setUp(self):
        os.environ["NO_PROXY"] = "127.0.0.1,localhost"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "index").mkdir(parents=True)
        (self.root / "templates").mkdir(parents=True)
        (self.root / "dataset" / "beauty-cosmetics").mkdir(parents=True)

        self.sample_pin = {
            "pin_id": "888001",
            "pin_url": "https://www.pinterest.com/pin/888001/",
            "image_url": "https://i.pinimg.com/orig/888001.jpg",
            "title": "Minimalist Hydrating Face Serum Ad",
            "description": "Don't settle for dry skin. Organic botanical formula with hyaluronic acid. Shop now.",
            "alt_text": "Amber glass serum bottle on travertine stone pedestal",
            "query": "skincare ad design",
            "industry": "beauty-cosmetics",
            "format": "ad-creative",
            "width": 1080,
            "height": 1350,
            "saved_width": 1080,
            "saved_height": 1350,
            "aspect_ratio": 0.8,
            "palette": ["#f5ede3", "#3c2a21", "#d4a373", "#faedcd", "#e9edc9"],
            "caption": "Minimalist Hydrating Face Serum Ad. Amber glass serum bottle on travertine stone pedestal.",
            "image_path": "dataset/beauty-cosmetics/888001.jpg",
            "caption_path": "dataset/beauty-cosmetics/888001.txt",
            "collected_at": "2026-10-23T10:00:00+00:00",
        }

        with open(self.root / "index" / "pins.jsonl", "w", encoding="utf-8") as f:
            f.write(json.dumps(self.sample_pin) + "\n")

        # Real tiny JPEG image
        from PIL import Image
        import io
        img_buf = io.BytesIO()
        Image.new("RGB", (10, 10), (245, 237, 227)).save(img_buf, "JPEG")
        (self.root / "dataset" / "beauty-cosmetics" / "888001.jpg").write_bytes(img_buf.getvalue())

        # Start server on ephemeral port
        self.httpd, self.port = server.create_server(host="127.0.0.1", port=0, repo_dir=self.root)
        import threading
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.temp_dir.cleanup()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def test_heuristic_analysis(self):
        analysis = design_analyzer.heuristic_analyze(self.sample_pin)
        self.assertEqual(analysis["pin_id"], "888001")
        self.assertEqual(analysis["industry_slug"], "beauty-cosmetics")
        self.assertIn("layout", analysis)
        self.assertIn("typography", analysis)
        self.assertIn("colors", analysis)
        self.assertIn("design_aesthetic", analysis)
        self.assertIn("prompt_templates", analysis)

        # Check layout properties
        layout = analysis["layout"]
        self.assertEqual(layout["aspect_ratio_code"], "4:5")
        self.assertIn("Hero", layout["layout_type"])

        # Check typography properties
        typo = analysis["typography"]
        self.assertTrue(len(typo["recommended_headline_fonts"]) > 0)
        self.assertIn("Serif", typo["headline_font_style"])

        # Check prompt templates
        templates = analysis["prompt_templates"]
        self.assertIn("nano_banana", templates)
        self.assertIn("nano_banana_edit", templates)
        self.assertNotIn("midjourney", templates)
        self.assertNotIn("flux", templates)
        self.assertIn("4K resolution", templates["nano_banana"])
        self.assertIn("4K resolution", templates["nano_banana_edit"])
        self.assertIn("Amber glass serum bottle", templates["nano_banana"])
        self.assertIn("3-tier vertical hierarchy", templates["nano_banana"])
        self.assertIn("{{BRAND_NAME}}", templates["creative_ad"])
        self.assertIn(":root", templates["figma_specs"])

    def test_template_persistence(self):
        analysis = design_analyzer.heuristic_analyze(self.sample_pin)
        tpl_record = {
            "title": "Beauty Serum Campaign",
            "pin_id": "888001",
            "industry": "beauty-cosmetics",
            "movement": "Organic Luxury Minimalist",
            "prompt_templates": analysis["prompt_templates"],
        }
        saved = design_analyzer.save_template_record(self.root, tpl_record)
        self.assertTrue(saved["id"].startswith("tpl_"))

        # Verify list
        saved_list = design_analyzer.list_saved_templates(self.root)
        self.assertEqual(len(saved_list), 1)
        self.assertEqual(saved_list[0]["id"], saved["id"])

        # Verify markdown file was written
        md_file = self.root / "templates" / f"{saved['id']}.md"
        self.assertTrue(md_file.exists())
        self.assertIn("Beauty Serum Campaign", md_file.read_text(encoding="utf-8"))

        # Delete
        deleted = design_analyzer.delete_template_record(self.root, saved["id"])
        self.assertTrue(deleted)
        self.assertEqual(len(design_analyzer.list_saved_templates(self.root)), 0)
        self.assertFalse(md_file.exists())

    def test_server_analyze_and_generate_api(self):
        # 1. POST /api/analyze-pin
        req_data = json.dumps({"pin_id": "888001"}).encode("utf-8")
        req = urllib.request.Request(
            self._url("/api/analyze-pin"),
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "ok")
            analysis = data["analysis"]
            self.assertEqual(analysis["pin_id"], "888001")
            self.assertIn("prompt_templates", analysis)

        # 2. POST /api/generate-prompt with customized variables
        custom_req = json.dumps({
            "analysis": analysis,
            "customizations": {
                "brand_name": "Lumière Glow",
                "product_name": "Peptide Renewal Drops",
                "headline": "Awaken Your Skin's Radiance",
                "cta": "Shop Lumière",
            },
        }).encode("utf-8")
        req2 = urllib.request.Request(
            self._url("/api/generate-prompt"),
            data=custom_req,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2) as resp:
            self.assertEqual(resp.status, 200)
            res = json.loads(resp.read().decode("utf-8"))
            creative = res["prompt_templates"]["creative_ad"]
            self.assertIn("Lumière Glow", creative)
            self.assertIn("Peptide Renewal Drops", creative)
            self.assertIn("Awaken Your Skin's Radiance", creative)

        # 3. POST /api/templates
        save_req = json.dumps({
            "title": "Lumiere Template",
            "pin_id": "888001",
            "industry": "beauty-cosmetics",
            "prompt_templates": res["prompt_templates"],
        }).encode("utf-8")
        req3 = urllib.request.Request(
            self._url("/api/templates"),
            data=save_req,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req3) as resp:
            self.assertEqual(resp.status, 201)
            saved_resp = json.loads(resp.read().decode("utf-8"))
            tpl_id = saved_resp["template"]["id"]

        # 4. GET /api/templates
        with urllib.request.urlopen(self._url("/api/templates")) as resp:
            self.assertEqual(resp.status, 200)
            t_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(len(t_data["templates"]), 1)
            self.assertEqual(t_data["templates"][0]["id"], tpl_id)

        # 5. DELETE /api/templates/<id>
        del_req = urllib.request.Request(
            self._url(f"/api/templates/{tpl_id}"),
            method="DELETE",
        )
        with urllib.request.urlopen(del_req) as resp:
            self.assertEqual(resp.status, 200)
            del_resp = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(del_resp["status"], "deleted")


if __name__ == "__main__":
    unittest.main()
