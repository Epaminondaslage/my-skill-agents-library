import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import enrich  # noqa: E402


def item(**overrides):
    base = {
        "id": "abc123", "name": "foo", "repo": "o/f", "url": "", "stars": 0,
        "function": "Reviews pull requests for bugs", "dev_note": "1/10",
        "kind": "skill", "purpose": "other", "status": "candidata",
        "personal_note": "", "decided_at": None,
        "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


class TestEnrichItems(unittest.TestCase):
    def test_enriches_url_stars_kind_purpose(self):
        def fake_fetch(url):
            self.assertEqual(url, "https://api.github.com/repos/o/f")
            return {"html_url": "https://github.com/o/f", "stargazers_count": 99}

        result = enrich.enrich_items([item()], fetch_fn=fake_fetch)
        self.assertEqual(result[0]["url"], "https://github.com/o/f")
        self.assertEqual(result[0]["stars"], 99)
        self.assertEqual(result[0]["kind"], "skill")
        self.assertEqual(result[0]["purpose"], "devops")  # "pull request" matches devops pattern first

    def test_missing_repo_keeps_existing_data_and_does_not_crash(self):
        def failing_fetch(url):
            raise OSError("404")

        result = enrich.enrich_items([item(repo="o/does-not-exist")], fetch_fn=failing_fetch)
        self.assertEqual(result[0]["repo"], "o/does-not-exist")
        self.assertEqual(result[0]["stars"], 0)  # unchanged, not crashed

    def test_preserves_untouched_fields(self):
        result = enrich.enrich_items(
            [item(personal_note="minha nota", status="aprovada")],
            fetch_fn=lambda url: {"html_url": "https://github.com/o/f", "stargazers_count": 1},
        )
        self.assertEqual(result[0]["personal_note"], "minha nota")
        self.assertEqual(result[0]["status"], "aprovada")


class TestEnrichMain(unittest.TestCase):
    def test_main_rewrites_items_json_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_path = Path(tmp) / "items.json"
            items_path.write_text(json.dumps([item()]), encoding="utf-8")
            enrich.main(
                items_path,
                fetch_fn=lambda url: {"html_url": "https://github.com/o/f", "stargazers_count": 5},
            )
            saved = json.loads(items_path.read_text(encoding="utf-8"))
            self.assertEqual(saved[0]["stars"], 5)


if __name__ == "__main__":
    unittest.main()
