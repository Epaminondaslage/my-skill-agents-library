#!/usr/bin/env python3
# =============================================================================
# serve.py — Unix-socket JSON server wiring for the SkillLibrary backend.
# One nginx location proxies exactly this socket. Never spawns a process;
# mutations only ever write items.json + regen.request (see api.py).
# =============================================================================

from __future__ import annotations

import json
import os
import socketserver
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from api import ApiError, SkillLibrary, check_password

SOCKET_PATH = os.environ.get("SKILL_LIBRARY_SOCKET", "/run/skill-agents-library/sock")

WRITE_ACTIONS = {"add", "edit", "delete", "set_status", "set_note"}


class Handler(BaseHTTPRequestHandler):
    lib = SkillLibrary()

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            req = json.loads(raw or b"{}")
            action = req.get("action")

            if action in WRITE_ACTIONS and not check_password(req.get("password", "")):
                raise ApiError(401, "senha inválida", code="bad_password")

            if action == "list":
                result = self.lib.list_items()
            elif action == "add":
                result = self.lib.add_item(
                    name=req.get("name", ""),
                    repo=req.get("repo", ""),
                    stars=req.get("stars", ""),
                    function=req.get("function", ""),
                    dev_note=req.get("dev_note", ""),
                )
            elif action == "edit":
                fields = {k: req.get(k) for k in ("name", "repo", "stars", "function", "dev_note")}
                result = self.lib.edit_item(req.get("id"), **fields)
            elif action == "delete":
                self.lib.delete_item(req.get("id"))
                result = {"ok": True}
            elif action == "set_status":
                result = self.lib.set_status(req.get("id"), req.get("status"))
            elif action == "set_note":
                result = self.lib.set_note(req.get("id"), req.get("personal_note", ""))
            else:
                raise ApiError(400, f"ação desconhecida: {action}", code="unknown_action")

            self._send_json(200, result if isinstance(result, dict) else {"items": result})
        except ApiError as exc:
            self._send_json(exc.status, exc.payload)
        except Exception as exc:  # noqa: BLE001 — last-resort JSON error, never a stack trace to the client
            self._send_json(500, {"error": str(exc), "code": "internal_error"})

    def log_message(self, format, *args):  # noqa: A002 — silence default stderr logging
        pass


class UnixHTTPServer(socketserver.UnixStreamServer):
    allow_reuse_address = True


def run(socket_path: str = SOCKET_PATH) -> None:
    sock_dir = Path(socket_path).parent
    sock_dir.mkdir(parents=True, exist_ok=True)
    if Path(socket_path).exists():
        Path(socket_path).unlink()
    server = UnixHTTPServer(socket_path, Handler)
    os.chmod(socket_path, 0o660)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
