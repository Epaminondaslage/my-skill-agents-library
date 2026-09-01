#!/usr/bin/env python3
# =============================================================================
# api.py — CRUD backend for My Skill-Agents Library
# -----------------------------------------------------------------------------
# Standard library only. This module owns the business logic (SkillLibrary);
# the Unix-socket/HTTP wiring lives in serve.py (Task 5) so the logic here
# stays testable without a running server.
#
# Auth reuses my-Harness-Library's password hash at
# ~/.claude/.inventory/auth.hash — read-only, never written or duplicated
# here.
# =============================================================================

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

STATUSES = ("candidata", "aprovada", "rejeitada")

HOME = Path(os.environ.get("HOME", "")).expanduser()
CLAUDE = HOME / ".claude"
STATE = CLAUDE / ".skill-library"
ITEMS_FILE = STATE / "items.json"
REQUEST_FILE = STATE / "regen.request"
HARNESS_AUTH_FILE = CLAUDE / ".inventory" / "auth.hash"

EDITABLE_FIELDS = ("name", "repo", "stars", "function", "dev_note")


class ApiError(Exception):
    """Error carrying the HTTP status and the stable code the UI translates."""

    def __init__(self, status: int, message: str, code: str = ""):
        super().__init__(message)
        self.status = status
        self.payload = {"error": message}
        if code:
            self.payload["code"] = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_password(plain: str, auth_path: Path = HARNESS_AUTH_FILE) -> bool:
    """Verify plain against the harness's scrypt$n$r$p$salt$key hash file."""
    if not auth_path.exists():
        return False
    try:
        scheme, n, r, p, salt_hex, key_hex = auth_path.read_text(encoding="utf-8").strip().split("$")
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(key_hex)
        candidate = hashlib.scrypt(
            plain.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
        return hmac.compare_digest(candidate, expected)
    except (ValueError, OSError):
        return False


class SkillLibrary:
    def __init__(self, items_path: Path = ITEMS_FILE, request_path: Path = REQUEST_FILE):
        self.items_path = items_path
        self.request_path = request_path

    # -- persistence ---------------------------------------------------

    def _read(self) -> list[dict]:
        if not self.items_path.exists():
            return []
        return json.loads(self.items_path.read_text(encoding="utf-8"))

    def _write(self, items: list[dict]) -> None:
        self.items_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.items_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, self.items_path)
        self._queue_regen()

    def _queue_regen(self) -> None:
        self.request_path.parent.mkdir(parents=True, exist_ok=True)
        self.request_path.write_text(_now(), encoding="utf-8")

    def _find(self, items: list[dict], item_id: str) -> dict:
        for item in items:
            if item["id"] == item_id:
                return item
        raise ApiError(404, f"item não encontrado: {item_id}", code="not_found")

    # -- reads -----------------------------------------------------------

    def list_items(self) -> list[dict]:
        return self._read()

    # -- writes ------------------------------------------------------------

    def add_item(self, name: str, repo: str, stars: str, function: str, dev_note: str) -> dict:
        name = (name or "").strip()
        if not name:
            raise ApiError(400, "name é obrigatório", code="invalid_name")
        now = _now()
        item = {
            "id": uuid.uuid4().hex,
            "name": name,
            "repo": (repo or "").strip(),
            "stars": (stars or "").strip(),
            "function": (function or "").strip(),
            "dev_note": (dev_note or "").strip(),
            "status": "candidata",
            "personal_note": "",
            "decided_at": None,
            "created_at": now,
            "updated_at": now,
        }
        items = self._read()
        items.append(item)
        self._write(items)
        return item

    def edit_item(self, item_id: str, **fields) -> dict:
        items = self._read()
        item = self._find(items, item_id)
        for key, value in fields.items():
            if key in EDITABLE_FIELDS and value is not None:
                item[key] = value
        item["updated_at"] = _now()
        self._write(items)
        return item

    def delete_item(self, item_id: str) -> None:
        items = self._read()
        self._find(items, item_id)  # raises if missing
        items = [i for i in items if i["id"] != item_id]
        self._write(items)

    def set_status(self, item_id: str, status: str) -> dict:
        if status not in STATUSES:
            raise ApiError(400, f"status inválido: {status}", code="invalid_status")
        items = self._read()
        item = self._find(items, item_id)
        item["status"] = status
        item["decided_at"] = _now() if status != "candidata" else None
        item["updated_at"] = _now()
        self._write(items)
        return item

    def set_note(self, item_id: str, personal_note: str) -> dict:
        items = self._read()
        item = self._find(items, item_id)
        item["personal_note"] = personal_note or ""
        item["updated_at"] = _now()
        self._write(items)
        return item
