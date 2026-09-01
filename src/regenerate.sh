#!/usr/bin/env bash
# regenerate.sh — regenerate the static site if a regen was requested, or
# unconditionally when run with "force". Never invoked by api.py/serve.py
# directly — only reads the request file they drop.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${HOME:-/root}"
STATE_DIR="$HOME_DIR/.claude/.skill-library"
ITEMS_FILE="$STATE_DIR/items.json"
REQUEST_FILE="$STATE_DIR/regen.request"
CATALOG_MD="$HOME_DIR/my-Harness-Library/Catalogo-de-Agent-Skills.md"

mode="${1:-cron}"  # cron | force

if [[ "$mode" == "cron" && ! -f "$REQUEST_FILE" ]]; then
  echo "no regen requested, nothing to do"
  exit 0
fi

# Snapshot the request before doing any work. A write that lands *during*
# regeneration rewrites this file; comparing afterwards is what stops us from
# deleting a request whose changes this pass did not include. The stamp is the
# file's own content (an ISO timestamp with microseconds, rewritten on every
# mutation) plus its mtime — content alone is finer-grained than the 1-second
# mtime resolution a same-second write would hide behind.
request_stamp=""
if [[ -f "$REQUEST_FILE" ]]; then
  request_stamp="$(cat "$REQUEST_FILE" 2>/dev/null || true)|$(stat -c %Y "$REQUEST_FILE" 2>/dev/null || true)"
fi

if [[ -f "$CATALOG_MD" ]]; then
  python3 "$REPO_ROOT/src/seed.py" "$CATALOG_MD" "$ITEMS_FILE" || true
else
  # Not fatal: the generator starts from an empty items.json and the catalog
  # can be dropped in later. Warned loudly so it shows up in the cron log.
  echo "warning: catalog not found at $CATALOG_MD — skipping seed" >&2
fi

python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT/src')
import generator
generator.build_site(generator.ITEMS_FILE)
"

if [[ -n "$request_stamp" ]]; then
  now_stamp="$(cat "$REQUEST_FILE" 2>/dev/null || true)|$(stat -c %Y "$REQUEST_FILE" 2>/dev/null || true)"
  if [[ "$now_stamp" == "$request_stamp" ]]; then
    rm -f "$REQUEST_FILE"
  else
    echo "a write arrived during regeneration — request kept for the next pass" >&2
  fi
fi

echo "regenerated $(date -u +%FT%TZ)"
