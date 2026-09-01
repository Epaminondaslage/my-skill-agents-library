import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import generator  # noqa: E402

ITEMS = [
    {
        "id": "abc123",
        "name": "grill-me",
        "repo": "mattpocock/skills",
        "stars": "242,8K",
        "function": "Questionar e validar arquitetura",
        "dev_note": "10/10",
        "status": "candidata",
        "personal_note": "",
        "decided_at": None,
        "created_at": "2026-09-01T00:00:00+00:00",
        "updated_at": "2026-09-01T00:00:00+00:00",
    }
]


class TestRenderIndexHtml(unittest.TestCase):
    def test_embeds_items_as_json(self):
        html = generator.render_index_html(ITEMS)
        self.assertIn("grill-me", html)
        self.assertIn('<script id="items-data" type="application/json">', html)

    def test_links_app_js_and_styles_css(self):
        html = generator.render_index_html(ITEMS)
        self.assertIn('src="app.js"', html)
        self.assertIn('href="styles.css"', html)

    def test_escapes_script_close_tag(self):
        evil = [{**ITEMS[0], "personal_note": "</script><script>alert(1)</script>"}]
        html = generator.render_index_html(evil)
        self.assertNotIn("</script><script>alert(1)</script>", html)


class TestBuildSite(unittest.TestCase):
    def test_writes_three_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_path = Path(tmp) / "items.json"
            items_path.write_text(json.dumps(ITEMS), encoding="utf-8")
            out_dir = Path(tmp) / "site"

            generator.build_site(items_path, out_dir)

            self.assertTrue((out_dir / "index.html").exists())
            self.assertTrue((out_dir / "app.js").exists())
            self.assertTrue((out_dir / "styles.css").exists())

    def test_raises_on_corrupt_items_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_path = Path(tmp) / "items.json"
            items_path.write_text("{not json", encoding="utf-8")
            out_dir = Path(tmp) / "site"

            with self.assertRaises(json.JSONDecodeError):
                generator.build_site(items_path, out_dir)


if __name__ == "__main__":
    unittest.main()
