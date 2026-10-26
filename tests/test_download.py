"""Unit tests for Pinterest pin and board downloading."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from src import classifier, config, download, scraper, storage


def make_test_image(size=(800, 1000), color=(50, 120, 220)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


class TestParseTarget(unittest.TestCase):
    def test_numeric_pin_id(self):
        r = scraper.parse_target("112590053177724123")
        self.assertEqual(r["type"], "pin")
        self.assertEqual(r["pin_id"], "112590053177724123")
        self.assertIn("112590053177724123", r["url"])

    def test_full_pin_url(self):
        r = scraper.parse_target("https://www.pinterest.com/pin/112590053177724123/")
        self.assertEqual(r["type"], "pin")
        self.assertEqual(r["pin_id"], "112590053177724123")

    def test_pin_url_with_title_slug(self):
        r = scraper.parse_target("https://www.pinterest.com/pin/clean-fintech-dashboard--112590053177724123/")
        self.assertEqual(r["type"], "pin")
        self.assertEqual(r["pin_id"], "112590053177724123")

    def test_short_pin_it_url(self):
        r = scraper.parse_target("https://pin.it/7xK9l0M")
        self.assertEqual(r["type"], "pin_short")
        self.assertIn("pin.it/7xK9l0M", r["url"])

    def test_board_url(self):
        r = scraper.parse_target("https://www.pinterest.com/designstudio/mobile-ui-inspiration/")
        self.assertEqual(r["type"], "board")
        self.assertEqual(r["username"], "designstudio")
        self.assertEqual(r["board_slug"], "mobile-ui-inspiration")

    def test_query_fallback(self):
        r = scraper.parse_target("fintech landing page poster")
        self.assertEqual(r["type"], "query")
        self.assertEqual(r["query"], "fintech landing page poster")


class TestDownloadHelpers(unittest.TestCase):
    def setUp(self):
        self.sample_pin = {
            "pin_id": "777001",
            "pin_url": "https://www.pinterest.com/pin/777001/",
            "image_url": "https://i.pinimg.com/originals/77/7001.jpg",
            "width": 800,
            "height": 1000,
            "title": "Minimalist Ceramic Coffee Mug Ad",
            "description": "Clean coffee poster mockup with typography",
            "alt_text": "Ceramic mug on wooden table",
            "dominant_color": "#d2b48c",
            "source_link": "https://example.com/shop",
            "source_domain": "example.com",
            "pinner": "coffeelover",
            "board": "Coffee Branding",
            "is_video": False,
            "is_promoted": False,
            "created_at": "2026-10-20T12:00:00",
            "query": "coffee poster",
        }
        self.test_img_bytes = make_test_image()

    def test_save_pin_to_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "my_downloads"
            ctx = MagicMock()

            with patch("src.download.download_image_bytes", return_value=self.test_img_bytes):
                saved = download.save_pin_to_folder(
                    ctx=ctx,
                    pin=self.sample_pin,
                    output_dir=out_dir,
                    save_meta=True,
                    industry="food-beverage",
                )

            self.assertIsNotNone(saved)
            self.assertTrue((out_dir / "777001.jpg").exists())
            self.assertTrue((out_dir / "777001.txt").exists())
            self.assertTrue((out_dir / "777001.json").exists())

            meta = json.loads((out_dir / "777001.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["pin_id"], "777001")
            self.assertEqual(meta["industry"], "food-beverage")
            self.assertIn("aspect_ratio", meta)

    def test_save_pin_to_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = storage.Dataset(Path(tmp))
            ctx = MagicMock()

            with patch("src.download.download_image_bytes", return_value=self.test_img_bytes):
                ok = download.save_pin_to_dataset(
                    ctx=ctx,
                    ds=ds,
                    pin=self.sample_pin,
                    industry="food-beverage",
                )

            self.assertTrue(ok)
            self.assertEqual(len(ds.records), 1)
            self.assertTrue((Path(tmp) / "dataset/food-beverage/777001.jpg").exists())
            self.assertTrue((Path(tmp) / "dataset/food-beverage/777001.txt").exists())

            # Attempt duplicate
            with patch("src.download.download_image_bytes", return_value=self.test_img_bytes):
                dup = download.save_pin_to_dataset(
                    ctx=ctx,
                    ds=ds,
                    pin={**self.sample_pin, "pin_id": "777002"},
                    industry="food-beverage",
                )
            self.assertFalse(dup)

    def test_download_targets_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "downloads"
            mock_ctx = MagicMock()

            with patch("src.download.open_context") as mock_open:
                mock_open.return_value.__enter__.return_value = mock_ctx
                with patch("src.download.fetch_pin", return_value=self.sample_pin):
                    with patch("src.download.download_image_bytes", return_value=self.test_img_bytes):
                        results = download.download_targets(
                            targets=["https://www.pinterest.com/pin/777001/"],
                            output_dir=out_dir,
                            save_to_dataset=False,
                            save_meta=True,
                            no_push=True,
                        )

            self.assertEqual(results["saved_folder"], 1)
            self.assertEqual(len(results["pins"]), 1)
            self.assertTrue((out_dir / "777001.jpg").exists())


if __name__ == "__main__":
    unittest.main()
