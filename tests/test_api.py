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


class TestAddItem(unittest.TestCase):
    def test_adds_item_with_candidata_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(
                name="foo", repo="org/foo", stars="1K", function="does foo", dev_note="7/10"
            )
            self.assertEqual(item["status"], "candidata")
            self.assertEqual(len(lib.list_items()), 1)

    def test_rejects_empty_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            with self.assertRaises(api.ApiError):
                lib.add_item(name="", repo="org/foo", stars="1K", function="x", dev_note="1/10")


class TestSetStatus(unittest.TestCase):
    def test_updates_status_and_decided_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")
            updated = lib.set_status(item["id"], "aprovada")
            self.assertEqual(updated["status"], "aprovada")
            self.assertIsNotNone(updated["decided_at"])

    def test_rejects_invalid_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")
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
            item = lib.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")
            updated = lib.set_note(item["id"], "vale a pena testar")
            self.assertEqual(updated["personal_note"], "vale a pena testar")


class TestEditItem(unittest.TestCase):
    def test_edits_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")
            updated = lib.edit_item(item["id"], name="bar", stars="2K")
            self.assertEqual(updated["name"], "bar")
            self.assertEqual(updated["stars"], "2K")
            self.assertEqual(updated["repo"], "o/f")  # untouched field kept


class TestDeleteItem(unittest.TestCase):
    def test_deletes_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")
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
            lib1.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")

            lib2 = api.SkillLibrary(items_path=items_path, request_path=request_path)
            self.assertEqual(len(lib2.list_items()), 1)


class TestQueueRegen(unittest.TestCase):
    def test_add_item_queues_regen(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            lib.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")
            self.assertTrue(lib.request_path.exists())


class TestFieldValidation(unittest.TestCase):
    def test_edit_rejects_non_string_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")
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
            item = lib.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")
            with self.assertRaises(api.ApiError) as ctx:
                lib.edit_item(item["id"], repo="x" * (api.MAX_SHORT_FIELD + 1))
            self.assertEqual(ctx.exception.payload["code"], "invalid_field")

    def test_edit_accepts_field_at_the_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")
            value = "x" * api.MAX_LONG_FIELD
            updated = lib.edit_item(item["id"], function=value)
            self.assertEqual(updated["function"], value)

    def test_add_rejects_non_string_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            with self.assertRaises(api.ApiError) as ctx:
                lib.add_item(name="foo", repo={"o": "f"}, stars="", function="", dev_note="")
            self.assertEqual(ctx.exception.payload["code"], "invalid_field")

    def test_set_note_rejects_non_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")
            with self.assertRaises(api.ApiError) as ctx:
                lib.set_note(item["id"], {"nested": True})
            self.assertEqual(ctx.exception.payload["code"], "invalid_field")

    def test_set_note_rejects_over_length(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = make_lib(tmp)
            item = lib.add_item(name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10")
            with self.assertRaises(api.ApiError) as ctx:
                lib.set_note(item["id"], "n" * (api.MAX_LONG_FIELD + 1))
            self.assertEqual(ctx.exception.payload["code"], "invalid_field")


class TestCheckPassword(unittest.TestCase):
    def test_returns_false_when_auth_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist.hash"
            self.assertFalse(api.check_password("anything", auth_path=missing))

    def test_matches_hash_written_by_harness_scheme(self):
        import hashlib
        import secrets

        with tempfile.TemporaryDirectory() as tmp:
            auth_path = Path(tmp) / "auth.hash"
            salt = secrets.token_bytes(16)
            key = hashlib.scrypt(b"correct horse", salt=salt, n=2**14, r=8, p=1, dklen=32)
            auth_path.write_text(
                f"scrypt$16384$8$1${salt.hex()}${key.hex()}", encoding="utf-8"
            )
            self.assertTrue(api.check_password("correct horse", auth_path=auth_path))
            self.assertFalse(api.check_password("wrong", auth_path=auth_path))


if __name__ == "__main__":
    unittest.main()
