#!/usr/bin/env bash
# regenerate.sh — regenerate the static site if a regen was requested, or
# unconditionally when run from cron. Never invoked by api.py/serve.py
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

if [[ -f "$CATALOG_MD" ]]; then
  python3 "$REPO_ROOT/src/seed.py" "$CATALOG_MD" "$ITEMS_FILE" || true
fi

python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT/src')
import generator
generator.build_site(generator.ITEMS_FILE)
"

rm -f "$REQUEST_FILE"
echo "regenerated $(date -u +%FT%TZ)"
