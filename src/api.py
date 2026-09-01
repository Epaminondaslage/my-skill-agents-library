#!/usr/bin/env python3
# =============================================================================
# api.py — CRUD backend for My Skill-Agents Library
# -----------------------------------------------------------------------------
# Standard library only. This module owns the business logic (SkillLibrary);
# the Unix-socket/HTTP wiring lives in serve.py (Task 5) so the logic here
# stays testable without a running server.
# =============================================================================

from __future__ import annotations

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

EDITABLE_FIELDS = ("name", "repo", "stars", "function", "dev_note")

# Field length caps. Short identifiers stay short; prose fields get room but
# are still bounded so one item can never bloat items.json (nor the <script>
# payload the generator embeds) without limit.
MAX_SHORT_FIELD = 500  # name, repo, stars, dev_note
MAX_LONG_FIELD = 5000  # function, personal_note
FIELD_LIMITS = {
    "name": MAX_SHORT_FIELD,
    "repo": MAX_SHORT_FIELD,
    "stars": MAX_SHORT_FIELD,
    "dev_note": MAX_SHORT_FIELD,
    "function": MAX_LONG_FIELD,
    "personal_note": MAX_LONG_FIELD,
}


class ApiError(Exception):
    """Error carrying the HTTP status and the stable code the UI translates."""

    def __init__(self, status: int, message: str, code: str = ""):
        super().__init__(message)
        self.status = status
        self.payload = {"error": message}
        if code:
            self.payload["code"] = code


def _validate_field(key: str, value) -> str:
    """Reject non-strings and over-long values before they reach items.json."""
    if not isinstance(value, str):
        raise ApiError(400, f"{key} deve ser texto", code="invalid_field")
    limit = FIELD_LIMITS.get(key, MAX_SHORT_FIELD)
    if len(value) > limit:
        raise ApiError(400, f"{key} excede {limit} caracteres", code="invalid_field")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        values = {
            "name": name,
            "repo": repo,
            "stars": stars,
            "function": function,
            "dev_note": dev_note,
        }
        clean = {
            key: _validate_field(key, "" if value is None else value).strip()
            for key, value in values.items()
        }
        if not clean["name"]:
            raise ApiError(400, "name é obrigatório", code="invalid_name")
        now = _now()
        item = {
            "id": uuid.uuid4().hex,
            "name": clean["name"],
            "repo": clean["repo"],
            "stars": clean["stars"],
            "function": clean["function"],
            "dev_note": clean["dev_note"],
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
        # Validate everything before mutating anything: a rejected field must
        # not leave the item half-updated.
        clean = {
            key: _validate_field(key, value)
            for key, value in fields.items()
            if key in EDITABLE_FIELDS and value is not None
        }
        items = self._read()
        item = self._find(items, item_id)
        item.update(clean)
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
        note = _validate_field("personal_note", "" if personal_note is None else personal_note)
        items = self._read()
        item = self._find(items, item_id)
        item["personal_note"] = note
        item["updated_at"] = _now()
        self._write(items)
        return item
