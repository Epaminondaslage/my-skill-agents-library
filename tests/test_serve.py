"""Tests for serve.py — request routing and error shapes.

Each test drives a real serve.py server over a real Unix socket in a temp
directory, speaking HTTP over it by hand (http.client has no Unix transport).
"""

import http.client
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import api  # noqa: E402
import serve  # noqa: E402


class UnixHTTPConnection(http.client.HTTPConnection):
    """http.client over an AF_UNIX socket."""

    def __init__(self, socket_path):
        super().__init__("localhost")
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


class ServeTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)

        self.items_path = tmp / "items.json"
        self.items_path.write_text("[]", encoding="utf-8")

        self._orig_lib = serve.Handler.lib
        serve.Handler.lib = api.SkillLibrary(
            items_path=self.items_path, request_path=tmp / "regen.request"
        )

        self.socket_path = str(tmp / "sock")
        self.server = serve.UnixHTTPServer(self.socket_path, serve.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.tearDownServer)

    def tearDownServer(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        serve.Handler.lib = self._orig_lib
        self.tmp.cleanup()

    def post(self, payload):
        conn = UnixHTTPConnection(self.socket_path)
        try:
            conn.request(
                "POST",
                "/",
                body=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read() or b"{}")
        finally:
            conn.close()

    def seed_one(self):
        item = serve.Handler.lib.add_item(
            name="foo", repo="o/f", function="x", dev_note="1/10"
        )
        return item["id"]


class TestReadsAndWrites(ServeTestCase):
    def test_list_succeeds(self):
        status, body = self.post({"action": "list"})
        self.assertEqual(status, 200)
        self.assertEqual(body["items"], [])

    def test_add_succeeds(self):
        status, body = self.post(
            {
                "action": "add",
                "name": "grill-me",
                "repo": "o/g",
                "function": "x",
                "dev_note": "10/10",
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["name"], "grill-me")
        self.assertEqual(body["status"], "candidata")
        self.assertEqual(len(json.loads(self.items_path.read_text(encoding="utf-8"))), 1)

    def test_set_status_succeeds(self):
        item_id = self.seed_one()
        status, body = self.post(
            {"action": "set_status", "id": item_id, "status": "aprovada"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "aprovada")

    def test_delete_succeeds(self):
        item_id = self.seed_one()
        status, body = self.post({"action": "delete", "id": item_id})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(self.items_path.read_text(encoding="utf-8")), [])


class TestErrors(ServeTestCase):
    def test_unknown_action_is_400(self):
        status, body = self.post({"action": "obliterate"})
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "unknown_action")

    def test_missing_action_is_400(self):
        status, body = self.post({})
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "unknown_action")

    def test_non_string_field_is_rejected(self):
        item_id = self.seed_one()
        status, body = self.post(
            {"action": "edit", "id": item_id, "name": {"evil": 1}}
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "invalid_field")


class TestRefreshRepo(ServeTestCase):
    def test_refresh_repo_action_updates_item(self):
        item_id = self.seed_one()

        def fake_fetch(url):
            return {"html_url": "https://github.com/o/f", "stargazers_count": 7}

        orig = api.fetch_repo_info
        api.fetch_repo_info = lambda repo, fetch_fn=None: {"url": "https://github.com/o/f", "stars": 7}
        try:
            status, body = self.post({"action": "refresh_repo", "id": item_id})
        finally:
            api.fetch_repo_info = orig
        self.assertEqual(status, 200)
        self.assertEqual(body["stars"], 7)
        self.assertEqual(body["url"], "https://github.com/o/f")


if __name__ == "__main__":
    unittest.main()
