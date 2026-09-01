import contextlib
import io
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

    def test_missing_items_json_builds_an_empty_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_path = Path(tmp) / "items.json"  # deliberately never created
            out_dir = Path(tmp) / "site"

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                generator.build_site(items_path, out_dir)

            self.assertIn("warning", stderr.getvalue())
            self.assertTrue((out_dir / "index.html").exists())
            self.assertIn(
                '<script id="items-data" type="application/json">[]</script>',
                (out_dir / "index.html").read_text(encoding="utf-8"),
            )

    def test_raises_on_corrupt_items_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_path = Path(tmp) / "items.json"
            items_path.write_text("{not json", encoding="utf-8")
            out_dir = Path(tmp) / "site"

            with self.assertRaises(json.JSONDecodeError):
                generator.build_site(items_path, out_dir)


class TestRenderAppJsFilters(unittest.TestCase):
    def test_defines_kind_and_purpose_lists(self):
        js = generator.render_app_js()
        self.assertIn('const KINDS = ["skill", "agent", "command", "plugin", "mcp"]', js)
        self.assertIn("spec-ops", js)

    def test_renders_purpose_sections(self):
        js = generator.render_app_js()
        self.assertIn("function renderSections(", js)

    def test_card_shows_stars_and_repo_link(self):
        js = generator.render_app_js()
        self.assertIn("item.stars", js)
        self.assertIn('target = "_blank"', js.replace("target=", "target ="))  # tolerant of formatting

    def test_modal_has_refresh_button(self):
        js = generator.render_app_js()
        self.assertIn("refresh_repo", js)
        self.assertIn("atualizar do GitHub", js)

    def test_card_shows_purpose_badge(self):
        js = generator.render_app_js()
        self.assertIn('"badge badge-" + item.purpose', js)


class TestRenderStylesCssPurpose(unittest.TestCase):
    def test_defines_purpose_color_tokens(self):
        css = generator.render_styles_css()
        for token in (
            "--c-general-fg", "--c-devops-fg", "--c-spec-ops-fg", "--c-quality-fg",
            "--c-security-fg", "--c-integrations-fg", "--c-tooling-fg",
            "--c-frontend-fg", "--c-other-fg",
        ):
            self.assertIn(token, css)

    def test_defines_section_header_class(self):
        css = generator.render_styles_css()
        self.assertIn(".section-head", css)


if __name__ == "__main__":
    unittest.main()
