import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import api  # noqa: E402


def make_lib(tmp):
    items_path = Path(tmp) / "items.json"
    items_path.write_text("[]", encoding="utf-8")
    request_path = Path(tmp) / "regen.request"
    return api.SkillLibrary(items_path=items_path, request_path=request_path)


class TestClassify(unittest.TestCase):
    def test_classify_kind_defaults_to_skill(self):
        self.assertEqual(api.classify_kind("avoid-ai-writing", "Audit and rewrite content"), "skill")

    def test_classify_kind_detects_mcp(self):
        self.assertEqual(api.classify_kind("github-mcp", "An MCP server for GitHub"), "mcp")

    def test_classify_kind_detects_agent(self):
        self.assertEqual(api.classify_kind("cavecrew-investigator", "Read-only subagent"), "agent")

    def test_classify_kind_detects_command(self):
        self.assertEqual(api.classify_kind("/deploy-prod", "A slash command for prod deploys"), "command")

    def test_classify_kind_detects_plugin(self):
        self.assertEqual(api.classify_kind("caveman", "An ultra-compressed communication plugin"), "plugin")

    def test_classify_purpose_detects_security(self):
        self.assertEqual(api.classify_purpose("security-review", "Find vulnerabilities and secrets"), "security")

    def test_classify_purpose_falls_back_to_other(self):
        self.assertEqual(api.classify_purpose("mystery-thing", "does something unclassifiable xyzzy"), "other")


class TestAddItem(unittest.TestCase):
    def test_adds_item_with_candidata_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(
                name="foo", repo="org/foo", function="does foo", dev_note="7/10"
            )
            self.assertEqual(item["status"], "candidata")
            self.assertEqual(len(lib.list_items()), 1)

    def test_rejects_empty_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            with self.assertRaises(api.ApiError):
                lib.add_item(name="", repo="org/foo", function="x", dev_note="1/10")


class TestSetStatus(unittest.TestCase):
    def test_updates_status_and_decided_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            updated = lib.set_status(item["id"], "aprovada")
            self.assertEqual(updated["status"], "aprovada")
            self.assertIsNotNone(updated["decided_at"])

    def test_rejects_invalid_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            with self.assertRaises(api.ApiError):
                lib.set_status(item["id"], "nope")

    def test_unknown_id_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            with self.assertRaises(api.ApiError):
                lib.set_status("missing-id", "aprovada")


class TestSetNote(unittest.TestCase):
    def test_updates_personal_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            updated = lib.set_note(item["id"], "vale a pena testar")
            self.assertEqual(updated["personal_note"], "vale a pena testar")


class TestEditItem(unittest.TestCase):
    def test_edits_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            updated = lib.edit_item(item["id"], name="bar")
            self.assertEqual(updated["name"], "bar")
            self.assertEqual(updated["repo"], "o/f")  # untouched field kept


class TestDeleteItem(unittest.TestCase):
    def test_deletes_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            lib.delete_item(item["id"])
            self.assertEqual(lib.list_items(), [])

    def test_unknown_id_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            with self.assertRaises(api.ApiError):
                lib.delete_item("missing-id")


class TestPersistence(unittest.TestCase):
    def test_writes_survive_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_path = Path(tmp) / "items.json"
            items_path.write_text("[]", encoding="utf-8")
            request_path = Path(tmp) / "regen.request"

            lib1 = api.SkillLibrary(items_path=items_path, request_path=request_path)
            lib1.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")

            lib2 = api.SkillLibrary(items_path=items_path, request_path=request_path)
            self.assertEqual(len(lib2.list_items()), 1)


class TestQueueRegen(unittest.TestCase):
    def test_add_item_queues_regen(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            self.assertTrue(lib.request_path.exists())


class TestFieldValidation(unittest.TestCase):
    def test_edit_rejects_non_string_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            for bad in ({"a": 1}, ["x"], 7, True):
                with self.subTest(value=bad):
                    with self.assertRaises(api.ApiError) as ctx:
                        lib.edit_item(item["id"], name=bad)
                    self.assertEqual(ctx.exception.payload["code"], "invalid_field")
            # rejected before any mutation reached items.json
            self.assertEqual(lib.list_items()[0]["name"], "foo")

    def test_edit_rejects_over_length_short_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            with self.assertRaises(api.ApiError) as ctx:
                lib.edit_item(item["id"], repo="x" * (api.MAX_SHORT_FIELD + 1))
            self.assertEqual(ctx.exception.payload["code"], "invalid_field")

    def test_edit_accepts_field_at_the_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            value = "x" * api.MAX_LONG_FIELD
            updated = lib.edit_item(item["id"], function=value)
            self.assertEqual(updated["function"], value)

    def test_add_rejects_non_string_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            with self.assertRaises(api.ApiError) as ctx:
                lib.add_item(name="foo", repo={"o": "f"}, function="", dev_note="")
            self.assertEqual(ctx.exception.payload["code"], "invalid_field")

    def test_set_note_rejects_non_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            with self.assertRaises(api.ApiError) as ctx:
                lib.set_note(item["id"], {"nested": True})
            self.assertEqual(ctx.exception.payload["code"], "invalid_field")

    def test_set_note_rejects_over_length(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            with self.assertRaises(api.ApiError) as ctx:
                lib.set_note(item["id"], "n" * (api.MAX_LONG_FIELD + 1))
            self.assertEqual(ctx.exception.payload["code"], "invalid_field")


class TestAddItemSchema(unittest.TestCase):
    def test_add_item_derives_url_stars_kind_purpose(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(
                name="security-review", repo="org/sec-tool",
                function="Find vulnerabilities and secrets", dev_note="9/10",
            )
            self.assertEqual(item["url"], "https://github.com/org/sec-tool")
            self.assertEqual(item["stars"], 0)
            self.assertEqual(item["kind"], "skill")
            self.assertEqual(item["purpose"], "security")

    def test_add_item_blank_repo_gives_blank_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="", function="x", dev_note="1/10")
            self.assertEqual(item["url"], "")


class TestEditItemKindPurpose(unittest.TestCase):
    def test_edit_item_updates_kind_and_purpose(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            updated = lib.edit_item(item["id"], kind="agent", purpose="devops")
            self.assertEqual(updated["kind"], "agent")
            self.assertEqual(updated["purpose"], "devops")

    def test_edit_item_rejects_invalid_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            with self.assertRaises(api.ApiError) as ctx:
                lib.edit_item(item["id"], kind="bogus")
            self.assertEqual(ctx.exception.payload["code"], "invalid_kind")

    def test_edit_item_recomputes_url_from_new_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            updated = lib.edit_item(item["id"], repo="o/new-name")
            self.assertEqual(updated["url"], "https://github.com/o/new-name")


class TestRefreshRepo(unittest.TestCase):
    def test_refresh_repo_updates_url_and_stars(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")

            def fake_fetch(url):
                self.assertEqual(url, "https://api.github.com/repos/o/f")
                return {"html_url": "https://github.com/o/f", "stargazers_count": 42}

            updated = lib.refresh_repo(item["id"], fetch_fn=fake_fetch)
            self.assertEqual(updated["url"], "https://github.com/o/f")
            self.assertEqual(updated["stars"], 42)

    def test_refresh_repo_does_not_reclassify(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")
            lib.edit_item(item["id"], kind="agent", purpose="devops")

            def fake_fetch(url):
                return {"html_url": "https://github.com/o/f", "stargazers_count": 1}

            updated = lib.refresh_repo(item["id"], fetch_fn=fake_fetch)
            self.assertEqual(updated["kind"], "agent")
            self.assertEqual(updated["purpose"], "devops")

    def test_refresh_repo_wraps_fetch_failure_as_502(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", function="x", dev_note="1/10")

            def failing_fetch(url):
                raise OSError("network unreachable")

            with self.assertRaises(api.ApiError) as ctx:
                lib.refresh_repo(item["id"], fetch_fn=failing_fetch)
            self.assertEqual(ctx.exception.status, 502)
            self.assertEqual(ctx.exception.payload["code"], "repo_fetch_failed")


if __name__ == "__main__":
    unittest.main()
