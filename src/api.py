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
import re
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

STATUSES = ("candidata", "aprovada", "rejeitada")

KINDS = ("skill", "agent", "command", "plugin", "mcp")
PURPOSES = (
    "general", "devops", "spec-ops", "quality", "security",
    "integrations", "tooling", "frontend", "other",
)

# Order matters: first match wins. Checked before PURPOSE_RULES so a name
# like "github-mcp" is unambiguous about *kind* even though it will also
# match "integrations" for purpose.
KIND_RULES = (
    ("mcp", r"\bmcp\b|mcp server"),
    ("command", r"^/|slash command"),
    ("agent", r"\bagent\b|subagent"),
    ("plugin", r"\bplugin\b|marketplace"),
)

# Adapted from my-Harness-Library's inventory.py CATEGORY_RULES — same
# hues/labels so the two catalogs read as one taxonomy.
PURPOSE_RULES = (
    ("security",     r"secur|vulnerab|owasp|exploit|cve\b|secret|hardening|pentest"),
    ("spec-ops",     r"\bspec|plan(o|ning)?\b|roadmap|workflow|task|backlog|scaffold|tdd|brainstorm"),
    ("devops",       r"deploy|infra|terraform|docker|kubernet|ansible|ci[/-]?cd|pipeline|tunnel|cron|monitor|observab|cost|\bgit\b|worktree|\bcommit|branch|merge|pull request|\bpr\b|rebase"),
    ("quality",      r"review|audit|lint|refactor|simplif|moderniz|coverage|\btest|verific|valida|dead code|anti-pattern|legacy"),
    ("integrations", r"\bmcp server\b|connector|integrac|integrat|\bapi\b|webhook|crawl|scrap|browser"),
    ("tooling",      r"plugin|\bskill\b|\bhook\b|agent sdk|marketplace|claude code|slash command|subagent"),
    ("frontend",     r"frontend|front-end|\bui\b|\bux\b|design|css|componente|component|artifact"),
    ("general",      r"document|explica|explain|learn|ensin|escrit|writing|traduz|chat"),
)


def classify_kind(name: str, function: str) -> str:
    haystack = f"{name} {function}".lower()
    for kind, pattern in KIND_RULES:
        if re.search(pattern, haystack):
            return kind
    return "skill"


def classify_purpose(name: str, function: str) -> str:
    haystack = f"{name} {function}".lower()
    for purpose, pattern in PURPOSE_RULES:
        if re.search(pattern, haystack):
            return purpose
    return "other"

HOME = Path(os.environ.get("HOME", "")).expanduser()
CLAUDE = HOME / ".claude"
STATE = CLAUDE / ".skill-library"
ITEMS_FILE = STATE / "items.json"
REQUEST_FILE = STATE / "regen.request"

EDITABLE_FIELDS = ("name", "repo", "function", "dev_note")

# Field length caps. Short identifiers stay short; prose fields get room but
# are still bounded so one item can never bloat items.json (nor the <script>
# payload the generator embeds) without limit.
MAX_SHORT_FIELD = 500  # name, repo, dev_note
MAX_LONG_FIELD = 5000  # function, personal_note
FIELD_LIMITS = {
    "name": MAX_SHORT_FIELD,
    "repo": MAX_SHORT_FIELD,
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


def _repo_url(repo: str) -> str:
    return f"https://github.com/{repo}" if repo else ""


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "my-skill-agents-library", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_repo_info(repo: str, fetch_fn=None) -> dict:
    """GET the GitHub repo API for `repo` ("owner/name"). Returns
    {"url": str, "stars": int}. Any failure becomes ApiError(502,
    code="repo_fetch_failed") — refresh_repo never silently no-ops."""
    fetch_fn = fetch_fn or _http_get_json
    try:
        data = fetch_fn(f"https://api.github.com/repos/{repo}")
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError, TypeError) as exc:
        raise ApiError(502, f"falha ao consultar github: {exc}", code="repo_fetch_failed") from exc
    return {
        "url": data.get("html_url") or _repo_url(repo),
        "stars": int(data.get("stargazers_count", 0)),
    }


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

    def add_item(self, name: str, repo: str, function: str, dev_note: str) -> dict:
        values = {"name": name, "repo": repo, "function": function, "dev_note": dev_note}
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
            "url": _repo_url(clean["repo"]),
            "stars": 0,
            "function": clean["function"],
            "dev_note": clean["dev_note"],
            "kind": classify_kind(clean["name"], clean["function"]),
            "purpose": classify_purpose(clean["name"], clean["function"]),
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
        kind = fields.get("kind")
        if kind is not None and kind not in KINDS:
            raise ApiError(400, f"kind inválido: {kind}", code="invalid_kind")
        purpose = fields.get("purpose")
        if purpose is not None and purpose not in PURPOSES:
            raise ApiError(400, f"purpose inválido: {purpose}", code="invalid_purpose")

        items = self._read()
        item = self._find(items, item_id)
        item.update(clean)
        if kind is not None:
            item["kind"] = kind
        if purpose is not None:
            item["purpose"] = purpose
        if "repo" in clean:
            item["url"] = _repo_url(clean["repo"])
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

    def refresh_repo(self, item_id: str, fetch_fn=None) -> dict:
        items = self._read()
        item = self._find(items, item_id)
        info = fetch_repo_info(item["repo"], fetch_fn=fetch_fn)
        item["url"] = info["url"]
        item["stars"] = info["stars"]
        item["updated_at"] = _now()
        self._write(items)
        return item
