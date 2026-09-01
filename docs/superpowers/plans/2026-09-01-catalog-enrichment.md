# Catalog Enrichment (kind/purpose/stars/url + grouped UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify every catalog item by `kind`/`purpose`, replace placeholder `stars` text with real GitHub data, add a manual per-item refresh, and regroup the UI into purpose-colored sections with kind/purpose/sort filters.

**Architecture:** `api.py` gains a keyword-heuristic classifier (shared by `add_item` and the one-time `enrich.py` script) and a stdlib-`urllib` GitHub fetch used only by the new `refresh_repo` action — the sole network call in an otherwise offline backend. `generator.py`'s `render_app_js`/`render_styles_css` gain new filter rows, purpose-grouped rendering, and modal fields. No new files beyond `src/enrich.py` and its test.

**Tech Stack:** Python 3.9+ stdlib (`urllib.request` for the GitHub call), same vanilla DOM JS, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-01-catalog-enrichment-design.md`

## Global Constraints

- Stdlib-only, offline-first — the one exception is documented: `refresh_repo`'s GitHub GET via `urllib.request`.
- Backend must never spawn processes.
- State lives only under `~/.claude/.skill-library/`.
- `url` is always derived from `repo` (`https://github.com/<repo>`) or from the GitHub API's `html_url` after a refresh — never hand-entered.
- Manual `kind`/`purpose` edits are sticky: `refresh_repo` touches only `url`/`stars`, never reclassifies.
- Verify before claiming done: `python3 -m py_compile src/*.py`, `python3 -m unittest discover tests`, `node --check` the emitted `app.js`.

---

### Task 1: Classifier + schema migration in `api.py`

**Files:**
- Modify: `src/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces: `api.KINDS` (tuple), `api.PURPOSES` (tuple), `api.classify_kind(name: str, function: str) -> str`, `api.classify_purpose(name: str, function: str) -> str`.
- Produces: `SkillLibrary.add_item(name, repo, function, dev_note) -> dict` (drops the old `stars` param), item dict now has `url` (str), `stars` (int), `kind` (str), `purpose` (str).
- Produces: `SkillLibrary.edit_item(item_id, **fields) -> dict` accepts `kind`/`purpose` in addition to the existing editable fields, and recomputes `url` when `repo` is edited.

- [ ] **Step 1: Write the failing classifier tests**

Add to `tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest tests.test_api.TestClassify -v`
Expected: FAIL with `AttributeError: module 'api' has no attribute 'classify_kind'`

- [ ] **Step 3: Implement the classifier in `api.py`**

Add near the top of `src/api.py`, after the existing `STATUSES` constant:

```python
import re

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
```

- [ ] **Step 4: Run to verify the classifier tests pass**

Run: `python3 -m unittest tests.test_api.TestClassify -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "feat: add kind/purpose keyword classifier to api.py"
```

- [ ] **Step 6: Write the failing schema-migration tests**

Add to `tests/test_api.py` (replacing any existing `add_item`/`edit_item` calls that pass `stars=` — grep first: `grep -n 'stars=' tests/test_api.py`, update every call site to drop `stars=` since `add_item` no longer takes it):

```python
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
```

- [ ] **Step 7: Run to verify failure**

Run: `python3 -m unittest tests.test_api -v`
Expected: FAIL — `add_item()` still requires `stars`, `edit_item` doesn't know `kind`/`purpose`, item dicts lack `url`/`kind`/`purpose`.

- [ ] **Step 8: Implement the schema migration**

In `src/api.py`, replace `EDITABLE_FIELDS`:

```python
EDITABLE_FIELDS = ("name", "repo", "function", "dev_note")
```

Replace `FIELD_LIMITS` (drop `stars`, it is no longer a free-text field):

```python
FIELD_LIMITS = {
    "name": MAX_SHORT_FIELD,
    "repo": MAX_SHORT_FIELD,
    "dev_note": MAX_SHORT_FIELD,
    "function": MAX_LONG_FIELD,
    "personal_note": MAX_LONG_FIELD,
}
```

Add a helper next to `_validate_field`:

```python
def _repo_url(repo: str) -> str:
    return f"https://github.com/{repo}" if repo else ""
```

Replace `add_item`:

```python
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
```

Replace `edit_item`:

```python
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
```

- [ ] **Step 9: Run to verify all api tests pass**

Run: `python3 -m unittest discover tests -v 2>&1 | tail -20`
Expected: PASS, no failures (fix any remaining `stars=` call sites the grep in Step 6 found)

- [ ] **Step 10: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "feat: add kind/purpose/url/stars(int) to the item schema"
```

---

### Task 2: `refresh_repo` — manual GitHub fetch

**Files:**
- Modify: `src/api.py`
- Modify: `src/serve.py`
- Test: `tests/test_api.py`
- Test: `tests/test_serve.py`

**Interfaces:**
- Consumes: `api.ApiError`, `SkillLibrary._find`, `SkillLibrary._write` (Task 1).
- Produces: `api.fetch_repo_info(repo: str, fetch_fn=None) -> dict` (`{"url": str, "stars": int}`), `SkillLibrary.refresh_repo(item_id: str, fetch_fn=None) -> dict`.
- Produces (serve.py): action `"refresh_repo"` handled alongside the existing actions, body `{"action": "refresh_repo", "id": "<item id>"}`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest tests.test_api.TestRefreshRepo -v`
Expected: FAIL with `AttributeError: 'SkillLibrary' object has no attribute 'refresh_repo'`

- [ ] **Step 3: Implement `fetch_repo_info` and `refresh_repo` in `src/api.py`**

Add imports at the top of `src/api.py`:

```python
import urllib.error
import urllib.request
```

Add after `_repo_url`:

```python
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
```

Add a method to `SkillLibrary`, right after `set_note`:

```python
def refresh_repo(self, item_id: str, fetch_fn=None) -> dict:
    items = self._read()
    item = self._find(items, item_id)
    info = fetch_repo_info(item["repo"], fetch_fn=fetch_fn)
    item["url"] = info["url"]
    item["stars"] = info["stars"]
    item["updated_at"] = _now()
    self._write(items)
    return item
```

- [ ] **Step 4: Run to verify the api tests pass**

Run: `python3 -m unittest tests.test_api -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "feat: add refresh_repo — manual per-item GitHub star/url fetch"
```

- [ ] **Step 6: Write the failing serve.py test**

Add to `tests/test_serve.py` (in `TestReadsAndWrites`, or a new class in the same file):

```python
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
```

- [ ] **Step 7: Run to verify failure**

Run: `python3 -m unittest tests.test_serve.TestRefreshRepo -v`
Expected: FAIL with `code: "unknown_action"` (400) instead of 200

- [ ] **Step 8: Wire the action into `src/serve.py`**

In `src/serve.py`'s `do_POST`, add an `elif` branch alongside `set_note` (before the `else: raise ApiError(...)`):

```python
            elif action == "refresh_repo":
                result = self.lib.refresh_repo(req.get("id"))
```

- [ ] **Step 9: Run to verify the serve tests pass**

Run: `python3 -m unittest discover tests -v 2>&1 | tail -20`
Expected: PASS, all tests green

- [ ] **Step 10: Commit**

```bash
git add src/serve.py tests/test_serve.py
git commit -m "feat: wire refresh_repo into serve.py's action dispatch"
```

---

### Task 3: `src/enrich.py` — one-time GitHub enrichment script

**Files:**
- Create: `src/enrich.py`
- Test: `tests/test_enrich.py`

**Interfaces:**
- Consumes: `api.fetch_repo_info`, `api.classify_kind`, `api.classify_purpose` (Tasks 1–2).
- Produces: `enrich.enrich_items(items: list[dict], fetch_fn=None) -> list[dict]` (pure function, no I/O — testable without touching disk), `enrich.main(items_path: Path, fetch_fn=None) -> None` (reads/writes `items.json` in place, same tmp+replace pattern as `api.py`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_enrich.py`:

```python
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
        self.assertEqual(result[0]["purpose"], "quality")  # "reviews" matches quality

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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest tests.test_enrich -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'enrich'`

- [ ] **Step 3: Implement `src/enrich.py`**

```python
#!/usr/bin/env python3
# =============================================================================
# enrich.py — one-time enrichment: fills url/stars from GitHub and classifies
# kind/purpose for every item in items.json. Never invoked by serve.py/api.py
# or cron — run by hand, like seed.py, whenever the catalog needs a refresh
# of the items it doesn't already have per-item "atualizar do GitHub" for.
# =============================================================================

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from api import classify_kind, classify_purpose, fetch_repo_info, ApiError  # noqa: E402


def enrich_items(items: list[dict], fetch_fn=None) -> list[dict]:
    """Returns a new list with url/stars/kind/purpose filled in. A repo that
    fails to fetch (404, network error) keeps its existing url/stars and is
    reported to stderr — it never raises, so one bad repo doesn't abort the
    other 29."""
    result = []
    for original in items:
        item = dict(original)
        item["kind"] = classify_kind(item.get("name", ""), item.get("function", ""))
        item["purpose"] = classify_purpose(item.get("name", ""), item.get("function", ""))
        repo = item.get("repo", "")
        if repo:
            try:
                info = fetch_repo_info(repo, fetch_fn=fetch_fn)
                item["url"] = info["url"]
                item["stars"] = info["stars"]
            except ApiError as exc:
                print(f"warning: could not fetch {repo}: {exc}", file=sys.stderr)
        result.append(item)
    return result


def main(items_path: Path, fetch_fn=None) -> None:
    items = json.loads(items_path.read_text(encoding="utf-8"))
    enriched = enrich_items(items, fetch_fn=fetch_fn)
    tmp_path = items_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, items_path)
    print(f"enriched {len(enriched)} items -> {items_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: enrich.py <items.json>", file=sys.stderr)
        raise SystemExit(2)
    main(Path(sys.argv[1]))
```

- [ ] **Step 4: Run to verify the tests pass**

Run: `python3 -m unittest tests.test_enrich -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full suite**

Run: `python3 -m py_compile src/*.py && python3 -m unittest discover tests -v 2>&1 | tail -20`
Expected: PASS, no failures

- [ ] **Step 6: Commit**

```bash
git add src/enrich.py tests/test_enrich.py
git commit -m "feat: add one-time enrich.py — GitHub url/stars + kind/purpose classification"
```

---

### Task 4: Frontend — filters, purpose-grouped grid, badges, modal fields

**Files:**
- Modify: `src/generator.py` (`render_app_js`, `render_styles_css`)
- Test: `tests/test_generator.py`

**Interfaces:**
- Consumes: item fields `kind`, `purpose`, `url`, `stars` (Task 1).
- Produces: no new exported functions — `render_app_js()`/`render_styles_css()` keep their existing signatures; the emitted JS/CSS changes.

- [ ] **Step 1: Write the failing generator tests**

Add to `tests/test_generator.py`:

```python
class TestRenderAppJsFilters(unittest.TestCase):
    def test_defines_kind_and_purpose_lists(self):
        js = generator.render_app_js()
        self.assertIn('const KINDS = ["skill", "agent", "command", "plugin", "mcp"]', js)
        self.assertIn("spec-ops", js)

    def test_renders_purpose_sections(self):
        js = generator.render_app_js()
        self.assertIn("function renderSections(", js)

    def test_card_shows_stars_and_repo_link(self):
        js = generator.render_app_js()
        self.assertIn("item.stars", js)
        self.assertIn('target = "_blank"', js.replace("target=", "target ="))  # tolerant of formatting

    def test_modal_has_refresh_button(self):
        js = generator.render_app_js()
        self.assertIn("refresh_repo", js)
        self.assertIn("atualizar do GitHub", js)


class TestRenderStylesCssPurpose(unittest.TestCase):
    def test_defines_purpose_color_tokens(self):
        css = generator.render_styles_css()
        for token in (
            "--c-general-fg", "--c-devops-fg", "--c-spec-ops-fg", "--c-quality-fg",
            "--c-security-fg", "--c-integrations-fg", "--c-tooling-fg",
            "--c-frontend-fg", "--c-other-fg",
        ):
            self.assertIn(token, css)

    def test_defines_section_header_class(self):
        css = generator.render_styles_css()
        self.assertIn(".section-head", css)
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest tests.test_generator.TestRenderAppJsFilters tests.test_generator.TestRenderStylesCssPurpose -v`
Expected: FAIL — none of the new strings exist yet

- [ ] **Step 3: Rewrite the JS constants, state, and add helpers**

In `src/generator.py`'s `render_app_js()`, replace the top constants block:

```python
const API = "/skill-library/api";
const STATUSES = ["candidata", "aprovada", "rejeitada"];
const STATUS_LABEL = { candidata: "candidata", aprovada: "aprovada", rejeitada: "rejeitada" };
const KINDS = ["skill", "agent", "command", "plugin", "mcp"];
const KIND_LABEL = { skill: "Skills", agent: "Agents", command: "Commands", plugin: "Plugins", mcp: "MCPs" };
const PURPOSES = [
  "general", "devops", "spec-ops", "quality", "security",
  "integrations", "tooling", "frontend", "other",
];
const PURPOSE_LABEL = {
  general: "General", devops: "DevOps", "spec-ops": "Spec-Driven Ops", quality: "Quality",
  security: "Security", integrations: "Integrations", tooling: "Tooling",
  frontend: "Frontend", other: "Other",
};
const SORTS = ["default", "stars", "updated", "name"];
const SORT_LABEL = { default: "Padrão", stars: "Mais estrelas", updated: "Atualização recente", name: "Nome" };
const EDITABLE = ["name", "repo", "function", "dev_note"];

let items = [];
let filterStatus = null;
let filterKind = null;
let filterPurpose = null;
let sortBy = "default";
let openModalId = null; // id of the item whose modal is open, or null
```

- [ ] **Step 4: Add sort/filter helpers and the kind/purpose filter rows**

Add these functions right after `renderFilters` (which stays as the status filter — rename its comment to clarify, no signature change needed):

```javascript
function sortItems(list) {
  const sorted = list.slice();
  if (sortBy === "stars") sorted.sort((a, b) => (b.stars || 0) - (a.stars || 0));
  else if (sortBy === "updated") sorted.sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
  else if (sortBy === "name") sorted.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
  return sorted;
}

function countBy(list, key, value) {
  return list.filter((i) => (value === null ? true : i[key] === value)).length;
}

function renderPillRow(className, allLabel, options, labelFn, active, onPick, countFn) {
  const row = document.createElement("div");
  row.className = className;
  [null].concat(options).forEach((opt) => {
    const btn = document.createElement("button");
    btn.type = "button";
    const label = opt === null ? allLabel : labelFn(opt);
    const count = countFn ? countFn(opt) : null;
    btn.textContent = count === null ? label : label + " " + count;
    btn.className = "btn btn-sm" + (opt === active ? " btn-primary" : "");
    btn.onclick = () => onPick(opt);
    row.appendChild(btn);
  });
  return row;
}

function renderKindFilter() {
  return renderPillRow(
    "filters", "Todos", KINDS, (k) => KIND_LABEL[k], filterKind,
    (k) => { filterKind = k; render(); },
    (k) => countBy(items, "kind", k)
  );
}

function renderPurposeFilter() {
  return renderPillRow(
    "filters", "Todos", PURPOSES, (p) => PURPOSE_LABEL[p], filterPurpose,
    (p) => { filterPurpose = p; render(); },
    (p) => countBy(items, "purpose", p)
  );
}

function renderSortFilter() {
  return renderPillRow(
    "filters", null, SORTS, (s) => SORT_LABEL[s], sortBy,
    (s) => { sortBy = s || "default"; render(); },
    null
  );
}
```

Note: `renderSortFilter` passes `allLabel=null` — that produces an unwanted "null" pill. Fix `renderPillRow` to skip the leading `[null]` entry when `allLabel` is `null`:

```javascript
function renderPillRow(className, allLabel, options, labelFn, active, onPick, countFn) {
  const row = document.createElement("div");
  row.className = className;
  const withAll = allLabel === null ? options : [null].concat(options);
  withAll.forEach((opt) => {
    const btn = document.createElement("button");
    btn.type = "button";
    const label = opt === null ? allLabel : labelFn(opt);
    const count = countFn ? countFn(opt) : null;
    btn.textContent = count === null ? label : label + " " + count;
    btn.className = "btn btn-sm" + (opt === active ? " btn-primary" : "");
    btn.onclick = () => onPick(opt);
    row.appendChild(btn);
  });
  return row;
}
```

(Replace the whole `renderPillRow` function from the previous step with this corrected version — don't keep both.)

- [ ] **Step 5: Rewrite `render()` to group by purpose**

Replace the existing `render()` function body:

```javascript
function render() {
  const app = document.getElementById("app");
  while (app.firstChild) app.removeChild(app.firstChild);

  app.appendChild(renderTopbar());

  const container = document.createElement("div");
  container.className = "container";

  container.appendChild(renderFilters());
  container.appendChild(renderKindFilter());
  container.appendChild(renderPurposeFilter());
  container.appendChild(renderSortFilter());
  container.appendChild(renderAddForm());

  const filtered = items.filter(
    (i) =>
      (!filterStatus || i.status === filterStatus) &&
      (!filterKind || i.kind === filterKind) &&
      (!filterPurpose || i.purpose === filterPurpose)
  );

  container.appendChild(renderSections(filtered));

  app.appendChild(container);

  const openItem = items.find((i) => i.id === openModalId);
  if (openItem) app.appendChild(renderModal(openItem));
}

// One section per purpose (fixed order, empty ones omitted). The purpose
// filter above narrows to a single section instead of hiding the rest.
function renderSections(filtered) {
  const wrap = document.createElement("div");
  const purposesToShow = filterPurpose ? [filterPurpose] : PURPOSES;

  let any = false;
  purposesToShow.forEach((purpose) => {
    const group = sortItems(filtered.filter((i) => i.purpose === purpose));
    if (group.length === 0) return;
    any = true;

    const section = document.createElement("div");
    section.className = "purpose-section";

    const head = document.createElement("div");
    head.className = "section-head purpose-" + purpose;
    head.textContent = PURPOSE_LABEL[purpose] + " (" + group.length + ")";
    section.appendChild(head);

    const grid = document.createElement("div");
    grid.className = "grid";
    group.forEach((item) => grid.appendChild(renderItem(item)));
    section.appendChild(grid);

    wrap.appendChild(section);
  });

  if (!any) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "nenhum item aqui";
    wrap.appendChild(empty);
  }
  return wrap;
}
```

- [ ] **Step 6: Add kind/purpose badges, stars, and repo link to `renderItem`**

In `renderItem`, right after the existing `badge` (status) is appended to `head`, add:

```javascript
  const kindBadge = document.createElement("span");
  kindBadge.className = "badge badge-kind";
  kindBadge.textContent = KIND_LABEL[item.kind] || item.kind;
  head.appendChild(kindBadge);
```

Replace the existing `meta` block (repo/stars text) with a starred, linked version:

```javascript
  const meta = document.createElement("div");
  meta.className = "card-meta";
  const star = document.createElement("span");
  star.textContent = "★ " + (item.stars || 0);
  meta.appendChild(star);
  if (item.url) {
    const link = document.createElement("a");
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = item.repo || item.url;
    link.onclick = (e) => e.stopPropagation();
    meta.appendChild(document.createTextNode(" · "));
    meta.appendChild(link);
  } else if (item.repo) {
    meta.appendChild(document.createTextNode(" · " + item.repo));
  }
  card.appendChild(meta);
```

(This replaces the old two-line `meta.textContent = [item.repo, item.stars]...` block entirely.)

- [ ] **Step 7: Add kind/purpose selects and the refresh button to `renderModal`**

In `renderModal`, right after the existing `statusLabel`/`select` block (before `noteLabel`), add:

```javascript
  const kindLabel = document.createElement("label");
  kindLabel.textContent = "kind";
  const kindSelect = document.createElement("select");
  KINDS.forEach((k) => {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = KIND_LABEL[k];
    opt.selected = k === item.kind;
    kindSelect.appendChild(opt);
  });
  kindLabel.appendChild(kindSelect);
  body.appendChild(kindLabel);

  const purposeLabel = document.createElement("label");
  purposeLabel.textContent = "purpose";
  const purposeSelect = document.createElement("select");
  PURPOSES.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = PURPOSE_LABEL[p];
    opt.selected = p === item.purpose;
    purposeSelect.appendChild(opt);
  });
  purposeLabel.appendChild(purposeSelect);
  body.appendChild(purposeLabel);

  const repoInfo = document.createElement("div");
  repoInfo.className = "card-meta";
  repoInfo.id = "modal-repo-info";
  repoInfo.textContent = "★ " + (item.stars || 0) + (item.url ? " · " + item.url : "");
  body.appendChild(repoInfo);
```

In the `save.onclick` handler, add `kind`/`purpose` to the edit body:

```javascript
  save.onclick = () => {
    showError(err, "");
    const body2 = { id: item.id, kind: kindSelect.value, purpose: purposeSelect.value };
    EDITABLE.forEach((f) => {
      body2[f] = fields[f].value;
    });
    Promise.all([
      call("edit", body2),
      select.value !== item.status
        ? call("set_status", { id: item.id, status: select.value })
        : Promise.resolve(),
      note.value !== (item.personal_note || "")
        ? call("set_note", { id: item.id, personal_note: note.value })
        : Promise.resolve(),
    ])
      .then(() => {
        closeModal();
        reload();
      }, (ex) => handleError(ex, err));
  };
```

Add a refresh button right after `del` is appended to `actions` in `renderModal`:

```javascript
  const refresh = document.createElement("button");
  refresh.type = "button";
  refresh.className = "btn btn-sm";
  refresh.textContent = "atualizar do GitHub";
  refresh.onclick = () => {
    showError(err, "");
    call("refresh_repo", { id: item.id }).then((updated) => {
      item.stars = updated.stars;
      item.url = updated.url;
      repoInfo.textContent = "★ " + (item.stars || 0) + (item.url ? " · " + item.url : "");
    }, (ex) => handleError(ex, err));
  };
  actions.appendChild(refresh);
```

- [ ] **Step 8: Add the CSS tokens and section-header styles**

In `render_styles_css()`, add purpose color tokens next to the existing `--c-candidata-*` ones in `:root` (light theme):

```css
  --c-general-bg:      #e5e7eb; --c-general-fg:      #4b5563;
  --c-devops-bg:       #dcfce7; --c-devops-fg:        #15803d;
  --c-spec-ops-bg:     #e0e7ff; --c-spec-ops-fg:      #4338ca;
  --c-quality-bg:      #cffafe; --c-quality-fg:       #0e7490;
  --c-security-bg:     #fee2e2; --c-security-fg:      #b91c1c;
  --c-integrations-bg: #fef3c7; --c-integrations-fg:  #a16207;
  --c-tooling-bg:      #f3e8ff; --c-tooling-fg:       #7e22ce;
  --c-frontend-bg:     #fce7f3; --c-frontend-fg:      #be185d;
  --c-other-bg:        #f3f4f6; --c-other-fg:         #6b7280;
```

Add the matching dark-mode overrides in **both** the `@media (prefers-color-scheme: dark)` block and the `:root[data-theme="dark"]` block:

```css
    --c-general-bg:      #374151; --c-general-fg:      #d1d5db;
    --c-devops-bg:       #14532d; --c-devops-fg:       #86efac;
    --c-spec-ops-bg:     #312e81; --c-spec-ops-fg:     #a5b4fc;
    --c-quality-bg:      #164e63; --c-quality-fg:      #67e8f9;
    --c-security-bg:     #5c1f1f; --c-security-fg:     #fca5a5;
    --c-integrations-bg: #4a3410; --c-integrations-fg: #fcd34d;
    --c-tooling-bg:      #4a1d6b; --c-tooling-fg:      #d8b4fe;
    --c-frontend-bg:     #61123b; --c-frontend-fg:     #f9a8d4;
    --c-other-bg:        #2d3748; --c-other-fg:        #9ca3af;
```

Add new rules after the existing `.badge-rejeitada` rule:

```css
.badge-kind { background: var(--border); color: var(--body-txt); }
.badge-general      { background: var(--c-general-bg);      color: var(--c-general-fg); }
.badge-devops       { background: var(--c-devops-bg);       color: var(--c-devops-fg); }
.badge-spec-ops     { background: var(--c-spec-ops-bg);     color: var(--c-spec-ops-fg); }
.badge-quality      { background: var(--c-quality-bg);      color: var(--c-quality-fg); }
.badge-security     { background: var(--c-security-bg);     color: var(--c-security-fg); }
.badge-integrations { background: var(--c-integrations-bg); color: var(--c-integrations-fg); }
.badge-tooling      { background: var(--c-tooling-bg);      color: var(--c-tooling-fg); }
.badge-frontend     { background: var(--c-frontend-bg);     color: var(--c-frontend-fg); }
.badge-other        { background: var(--c-other-bg);        color: var(--c-other-fg); }

.purpose-section { margin-bottom: 1.5rem; }
.section-head {
  font-size: .85rem;
  font-weight: 600;
  padding: .4rem .7rem;
  margin-bottom: .6rem;
  border-radius: 8px;
  border-left: 4px solid var(--border);
}
.section-head.purpose-general      { border-left-color: var(--c-general-fg);      background: var(--c-general-bg);      color: var(--c-general-fg); }
.section-head.purpose-devops       { border-left-color: var(--c-devops-fg);       background: var(--c-devops-bg);       color: var(--c-devops-fg); }
.section-head.purpose-spec-ops     { border-left-color: var(--c-spec-ops-fg);     background: var(--c-spec-ops-bg);     color: var(--c-spec-ops-fg); }
.section-head.purpose-quality      { border-left-color: var(--c-quality-fg);      background: var(--c-quality-bg);      color: var(--c-quality-fg); }
.section-head.purpose-security     { border-left-color: var(--c-security-fg);     background: var(--c-security-bg);     color: var(--c-security-fg); }
.section-head.purpose-integrations { border-left-color: var(--c-integrations-fg); background: var(--c-integrations-bg); color: var(--c-integrations-fg); }
.section-head.purpose-tooling      { border-left-color: var(--c-tooling-fg);      background: var(--c-tooling-bg);      color: var(--c-tooling-fg); }
.section-head.purpose-frontend     { border-left-color: var(--c-frontend-fg);     background: var(--c-frontend-bg);     color: var(--c-frontend-fg); }
.section-head.purpose-other        { border-left-color: var(--c-other-fg);        background: var(--c-other-bg);        color: var(--c-other-fg); }

.card-meta a { color: var(--accent); text-decoration: none; }
.card-meta a:hover { text-decoration: underline; }
```

- [ ] **Step 9: Run to verify the generator tests pass**

Run: `python3 -m unittest tests.test_generator -v`
Expected: PASS

- [ ] **Step 10: Full verification pass**

Run:
```bash
python3 -m py_compile src/*.py
python3 -m unittest discover tests -v 2>&1 | tail -25
python3 -c "from src.generator import render_app_js; open('/tmp/app.js','w').write(render_app_js())"
node --check /tmp/app.js && echo NODE_OK
```
Expected: all PASS, `NODE_OK` printed, no compile errors

- [ ] **Step 11: Commit**

```bash
git add src/generator.py tests/test_generator.py
git commit -m "feat: purpose-grouped grid, kind/purpose/sort filters, stars+link on cards, refresh button in modal"
```

---

### Task 5: Run enrichment on the live catalog, document the network exception, deploy

**Files:**
- Modify: `CLAUDE.md` (document the `refresh_repo`/`enrich.py` network exception)
- No new tests — this task runs the already-tested script against real data and redeploys.

- [ ] **Step 1: Back up the live items.json**

```bash
cp ~/.claude/.skill-library/items.json ~/.claude/.skill-library/items.json.bak-2026-09-01
```

- [ ] **Step 2: Run the enrichment script against the real catalog**

```bash
cd /opt/my-skill-agents-library
python3 src/enrich.py ~/.claude/.skill-library/items.json
```

Expected: `enriched 30 items -> /home/epaminondas/.claude/.skill-library/items.json`, with any 404/network warnings on stderr for repos GitHub couldn't find (they keep their prior repo/stars, per `enrich_items`'s contract).

- [ ] **Step 3: Verify the enriched data**

```bash
python3 -c "
import json
items = json.load(open('/home/epaminondas/.claude/.skill-library/items.json'))
print(len(items), 'items')
for i in items[:5]:
    print(i['name'], '|', i['kind'], '|', i['purpose'], '|', i['stars'], '|', i['url'])
"
```

Expected: real integer star counts, non-empty `kind`/`purpose` for every item, plausible `url`s.

- [ ] **Step 4: Document the network exception in `CLAUDE.md`**

In `CLAUDE.md`, find the line `- The backend must never spawn processes — regeneration goes through` and add a new bullet right after that paragraph's list:

```markdown
- The one exception to "offline-first": `refresh_repo` (triggered by the
  modal's "atualizar do GitHub" button) makes a single stdlib `urllib`
  HTTPS GET to the GitHub API for that one item's repo. `src/enrich.py`
  makes the same call in bulk, but only when run by hand — never from
  serve.py, api.py, or cron.
```

- [ ] **Step 5: Commit the CLAUDE.md update**

```bash
git add CLAUDE.md
git commit -m "docs: note the refresh_repo/enrich.py network exception to offline-first"
```

- [ ] **Step 6: Rebuild and redeploy the Docker container**

```bash
docker compose up -d --build
docker exec skill-agents-library /app/src/regenerate.sh force
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8092/skill-library/
```

Expected: `200`

- [ ] **Step 7: Smoke-test the new action over the real socket**

```bash
ITEM_ID=$(curl -s -X POST http://localhost:8092/skill-library/api -H "Content-Type: application/json" -d '{"action":"list"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['items'][0]['id'])")
curl -s -X POST http://localhost:8092/skill-library/api -H "Content-Type: application/json" -d "{\"action\":\"refresh_repo\",\"id\":\"$ITEM_ID\"}"
```

Expected: JSON body with updated `stars`/`url` for that item, HTTP 200 (curl `-i` if you want to see the status line explicitly).

- [ ] **Step 8: Visual check**

Open `http://10.0.2.148:8092/skill-library/` and confirm: purpose-colored sections, kind/purpose/sort filter pills, star counts + clickable repo links on cards, and that the modal's kind/purpose selects and "atualizar do GitHub" button work.
