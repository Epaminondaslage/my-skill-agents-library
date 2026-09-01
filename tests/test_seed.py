import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import seed  # noqa: E402

SAMPLE_MD = """\
# Catálogo de Agent Skills. 31-08-2026

| # | Skill | Repositório GitHub | ⭐ Stars | 📦 Instalações | Função principal | Nota Dev |
|---:|---|---|---:|---:|---|:---:|
| 1 | `grill-me` | `mattpocock/skills` | ⭐ 242,8K | 1,0M | Questionar e validar arquitetura | 10/10 |
| 2 | `caveman` | `juliusbrussee/caveman` | ⭐ ~102K | 467,2K | Comunicação técnica compacta | 7/10 |

## Ranking recomendado para desenvolvimento

| Rank | Skill | Nota | Principal utilização |
|---:|---|:---:|---|
| 🥇 1 | `grill-me` | 10/10 | Validação de arquitetura |
"""


class TestParseCatalogMarkdown(unittest.TestCase):
    def test_parses_only_the_first_table(self):
        items = seed.parse_catalog_markdown(SAMPLE_MD)
        self.assertEqual(len(items), 2)

    def test_fields_mapped_correctly(self):
        items = seed.parse_catalog_markdown(SAMPLE_MD)
        first = items[0]
        self.assertEqual(first["name"], "grill-me")
        self.assertEqual(first["repo"], "mattpocock/skills")
        self.assertEqual(first["function"], "Questionar e validar arquitetura")
        self.assertEqual(first["dev_note"], "10/10")

    def test_stars_url_kind_purpose_match_add_item_schema(self):
        # The catalog's own "Stars" column is a placeholder, not a real
        # count — seeded items must share add_item's schema (int stars
        # starting at 0, derived url, classified kind/purpose) rather than
        # carrying the raw catalog text through.
        items = seed.parse_catalog_markdown(SAMPLE_MD)
        first = items[0]
        self.assertEqual(first["stars"], 0)
        self.assertEqual(first["url"], "https://github.com/mattpocock/skills")
        self.assertIn("kind", first)
        self.assertIn("purpose", first)

    def test_defaults(self):
        items = seed.parse_catalog_markdown(SAMPLE_MD)
        first = items[0]
        self.assertEqual(first["status"], "candidata")
        self.assertEqual(first["personal_note"], "")
        self.assertIsNone(first["decided_at"])
        self.assertTrue(first["id"])
        self.assertIn("created_at", first)
        self.assertIn("updated_at", first)

    def test_ignores_header_and_alignment_rows(self):
        items = seed.parse_catalog_markdown(SAMPLE_MD)
        names = [i["name"] for i in items]
        self.assertNotIn("Skill", names)


class TestImportCatalog(unittest.TestCase):
    def test_writes_items_json_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "catalog.md"
            md_path.write_text(SAMPLE_MD, encoding="utf-8")
            items_path = Path(tmp) / "items.json"

            result = seed.import_catalog(md_path, items_path)

            self.assertTrue(items_path.exists())
            on_disk = json.loads(items_path.read_text(encoding="utf-8"))
            self.assertEqual(len(on_disk), 2)
            self.assertEqual(result, on_disk)

    def test_does_not_overwrite_existing_items_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "catalog.md"
            md_path.write_text(SAMPLE_MD, encoding="utf-8")
            items_path = Path(tmp) / "items.json"
            existing = [{"id": "keep-me", "name": "already-here"}]
            items_path.write_text(json.dumps(existing), encoding="utf-8")

            result = seed.import_catalog(md_path, items_path)

            self.assertEqual(result, existing)
            on_disk = json.loads(items_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk, existing)


if __name__ == "__main__":
    unittest.main()
