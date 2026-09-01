"""Tests for serve.py — the auth gate is the whole security boundary.

Each test drives a real serve.py server over a real Unix socket in a temp
directory, speaking HTTP over it by hand (http.client has no Unix transport).
"""

import hashlib
import http.client
import json
import secrets
import socket
import tempfile
import threading
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import api  # noqa: E402
import serve  # noqa: E402

PASSWORD = "correct horse battery"


def write_auth_hash(path: Path, plain: str) -> None:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(plain.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    path.write_text(f"scrypt$16384$8$1${salt.hex()}${key.hex()}", encoding="utf-8")


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
        self.auth_path = tmp / "auth.hash"
        write_auth_hash(self.auth_path, PASSWORD)

        # Point both the library and the auth check at the temp state.
        self._orig_auth = api.HARNESS_AUTH_FILE
        api.HARNESS_AUTH_FILE = self.auth_path
        self._orig_default = api.check_password.__defaults__
        api.check_password.__defaults__ = (self.auth_path,)

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
        api.HARNESS_AUTH_FILE = self._orig_auth
        api.check_password.__defaults__ = self._orig_default
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
            name="foo", repo="o/f", stars="1K", function="x", dev_note="1/10"
        )
        return item["id"]


class TestReadsAreOpen(ServeTestCase):
    def test_list_succeeds_without_password(self):
        status, body = self.post({"action": "list"})
        self.assertEqual(status, 200)
        self.assertEqual(body["items"], [])


class TestAuthGate(ServeTestCase):
    def write_payloads(self):
        item_id = self.seed_one()
        return [
            {"action": "add", "name": "bar"},
            {"action": "edit", "id": item_id, "name": "bar"},
            {"action": "delete", "id": item_id},
            {"action": "set_status", "id": item_id, "status": "aprovada"},
            {"action": "set_note", "id": item_id, "personal_note": "nota"},
        ]

    def test_write_actions_401_without_password(self):
        for payload in self.write_payloads():
            with self.subTest(action=payload["action"]):
                status, body = self.post(payload)
                self.assertEqual(status, 401)
                self.assertEqual(body["code"], "bad_password")

    def test_write_actions_401_with_wrong_password(self):
        for payload in self.write_payloads():
            with self.subTest(action=payload["action"]):
                status, body = self.post({**payload, "password": "nope"})
                self.assertEqual(status, 401)
                self.assertEqual(body["code"], "bad_password")

    def test_nothing_is_written_when_auth_fails(self):
        self.post({"action": "add", "name": "sneaky"})
        self.assertEqual(json.loads(self.items_path.read_text(encoding="utf-8")), [])

    def test_correct_password_allows_a_write(self):
        status, body = self.post(
            {
                "action": "add",
                "password": PASSWORD,
                "name": "grill-me",
                "repo": "o/g",
                "stars": "1K",
                "function": "x",
                "dev_note": "10/10",
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["name"], "grill-me")
        self.assertEqual(body["status"], "candidata")
        self.assertEqual(len(json.loads(self.items_path.read_text(encoding="utf-8"))), 1)

    def test_correct_password_allows_set_status(self):
        item_id = self.seed_one()
        status, body = self.post(
            {"action": "set_status", "id": item_id, "status": "aprovada", "password": PASSWORD}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "aprovada")


class TestErrors(ServeTestCase):
    def test_unknown_action_is_400(self):
        status, body = self.post({"action": "obliterate", "password": PASSWORD})
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "unknown_action")

    def test_missing_action_is_400(self):
        status, body = self.post({})
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "unknown_action")

    def test_non_string_field_is_rejected(self):
        item_id = self.seed_one()
        status, body = self.post(
            {"action": "edit", "id": item_id, "name": {"evil": 1}, "password": PASSWORD}
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "invalid_field")


if __name__ == "__main__":
    unittest.main()
