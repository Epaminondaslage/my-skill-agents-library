# Catalog enrichment: kind/purpose taxonomy, real GitHub data, grouped UI

## Goal

Turn the 30 seeded catalog items into a properly classified, filterable,
groupable list — matching the taxonomy already used by my-Harness-Library's
inventory site (kind, purpose, real stars/url), grouped visually by purpose.

## Data model (items.json)

Add three fields to every item, alongside the existing
`name/repo/stars/function/dev_note/status/personal_note/*_at`:

- `url` (str) — `https://github.com/<repo>`, derived, never hand-edited.
- `stars` (int) — **replaces** the existing free-text `stars` field
  (`"242,8K"`, `"~102K"`, `"<1K"` were catalog-import placeholders, not real
  counts). Real `stargazers_count` from the GitHub API.
- `kind` (str enum) — one of `skill | agent | command | plugin | mcp`.
- `purpose` (str enum) — one of `general | devops | spec-ops | quality |
  security | integrations | tooling | frontend | other`.

`function` stays as-is: it is already a curated one-line PT-BR summary from
the catalog import, good enough as the card's description text — no new
summary field.

Backward compat: `stars` changes type (str → int). This is a one-time
migration via the enrichment script below; `_validate_field`/`FIELD_LIMITS`
in `api.py` need `stars` moved out of the string-field validation (it becomes
an int, validated separately), and `kind`/`purpose` added as validated enum
fields.

## Enrichment script (one-time, not a backend dependency)

New `src/enrich.py`, run manually (like `seed.py`), never invoked by
`serve.py`/`api.py`/cron:

1. For each item in `items.json`, `urllib.request` (stdlib) GETs
   `https://api.github.com/repos/<repo>`. Extracts `html_url` →`url`,
   `stargazers_count` → `stars`.
2. Classifies `kind` and `purpose` with a keyword-heuristic against
   `f"{name} {function}".lower()`, adapted from my-Harness-Library's
   `CATEGORY_RULES` (ordered regex, first match wins, `"other"` fallback).
   `kind` gets its own small rule set (mcp: `mcp server`; command: leading
   `/` or "slash command"; agent: "agent" / "subagent"; plugin: "plugin" /
   "marketplace"; default `skill`).
3. Writes the enriched `items.json` in place (same tmp-file+replace pattern
   as `api.py._write`). Prints a summary (N items updated, M repos not
   found — 404s keep the existing repo/stars and log a warning, they don't
   crash the run).
4. Unauthenticated GitHub API: 60 req/hour is enough for 30 items; no token
   needed, no new dependency (still stdlib `urllib`).

Run once now against the live `~/.claude/.skill-library/items.json`, then
queue a regen exactly like `api.py` does.

## Backend: manual per-item refresh

`api.py` gains `refresh_repo(item_id)`: same single-repo GitHub GET as the
script, re-classifies `kind`/`purpose` only if not already set by hand (an
item edited by the user keeps its manual classification — refresh only
touches `url`/`stars`, reclassifying is a distinct, explicit user action via
the modal, not automatic). Raises `ApiError(502, ..., code="repo_fetch_failed")`
on network failure or 404 — never silently no-ops so the UI can show why.

`serve.py` adds `"refresh_repo"` to the actions it recognizes (no password
gate exists any more, so this is just another POST action like `edit`).

This is the one exception to "the backend must never spawn processes /
stays offline": it makes an outbound HTTPS GET via stdlib `urllib`, nothing
else. Documented as a callout in `CLAUDE.md`'s working rules, scoped
strictly to this one action.

## Frontend

**Filter rows** (three, all pill-style like the existing status filters):
- **Kind**: Todos + 5 pills (Skills/Agents/Commands/Plugins/MCPs), each
  shows a live count of matching items.
- **Purpose**: Todos + 8 pills, colored per the existing badge palette
  (reuses/extends the `--c-*` tokens already defined for status, new ones
  for purpose categories — same hues as my-Harness-Library's `--c-*` set for
  visual consistency across the two apps).
- **Sort**: Padrão (catalog order) / Mais estrelas / Atualização recente
  (`updated_at`) / Nome — single-select pills, purely a display-order
  transform over the already-filtered list.

**Grouped grid**: default layout is one section per `purpose` (in a fixed
category order, empty categories omitted), each with a header — colored
left-border/label matching that purpose's badge color — and a count. Cards
render inside their section, sorted by the active sort. The purpose filter
narrows to a single section instead of hiding all others; the kind filter
and status filter apply within every visible section. Sort applies within
each section (not a global flatten), since grouping is the primary
structure now.

**Card**: gains a `kind` badge and a `purpose` badge (colored) next to the
existing status badge, a stars count (★ N), and the name/repo area becomes a
link to `url` (opens in a new tab, `rel="noopener"`) — clicking the link
itself must not open the edit modal (`stopPropagation`).

**Modal**: adds `kind`/`purpose` as `<select>` fields (same treatment as
`status`), a read-only stars/url display, and a "atualizar do GitHub" button
that calls `refresh_repo` and repaints those two read-only fields on success
without closing the modal.

## Testing

- `tests/test_enrich.py`: classification heuristic (table of name/function →
  expected kind+purpose), GitHub fetch mocked (no real network in tests),
  404 handling, in-place rewrite preserves untouched fields.
- `tests/test_api.py`: `refresh_repo` success/404/network-error paths
  (GitHub call injectable/mockable, same pattern as `check_password`'s old
  `auth_path` parameter — a `fetch_fn` parameter defaulting to the real
  urllib call).
- `tests/test_generator.py`: purpose section headers appear, cards carry the
  new badges/link — content assertions only, no browser test.
- Existing 36 tests must keep passing; `stars` type change means
  `test_api.py`/`test_generator.py` fixtures using string stars need
  updating to ints.

## Out of scope (explicit YAGNI)

- No cron-based periodic refresh (rejected in favor of the manual button).
- No GitHub auth/token — unauthenticated rate limit is sufficient for 30
  items refreshed rarely.
- No re-classification on every refresh (manual overrides are sticky).
- No changes to the `add` flow's required fields — `kind`/`purpose` default
  to heuristic classification on add, same as the enrichment script; `url`
  is derived, not entered.
