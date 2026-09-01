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
