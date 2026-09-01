#!/usr/bin/env python3
# =============================================================================
# seed.py — one-time importer: Catalogo-de-Agent-Skills.md -> items.json
# -----------------------------------------------------------------------------
# Parses only the FIRST markdown table in the file (the numbered catalog
# table). Every row becomes an item with status "candidata". Never overwrites
# an existing items.json — the JSON file is the source of truth after the
# first import.
# =============================================================================

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from api import classify_kind, classify_purpose

ROW_RE = re.compile(r"^\|(.+)\|\s*$")


def _clean_cell(cell: str) -> str:
    cell = cell.strip()
    cell = cell.strip("`")
    cell = re.sub(r"^⭐\s*", "", cell)
    return cell.strip()


def parse_catalog_markdown(md_text: str) -> list[dict]:
    """Parse the first markdown table in md_text into seed item dicts."""
    lines = md_text.splitlines()
    rows: list[list[str]] = []
    in_table = False
    for line in lines:
        m = ROW_RE.match(line)
        if not m:
            if in_table:
                break  # first table ended
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if not in_table:
            in_table = True
            continue  # header row
        if set("".join(cells)) <= set("-: "):
            continue  # alignment row (---:|---|...)
        rows.append(cells)

    now = datetime.now(timezone.utc).isoformat()
    items = []
    for cells in rows:
        # columns: # | Skill | Repo | Stars | Installs | Função | Nota Dev
        if len(cells) < 7:
            continue
        name = _clean_cell(cells[1])
        repo = _clean_cell(cells[2])
        function = _clean_cell(cells[5])
        # The catalog's own "Stars" column is a formatted placeholder
        # ("242,8K", "~102K", "<1K"), not a real count in a shape we can
        # parse — same schema as a freshly add_item()'d item: stars starts
        # at 0 and url/kind/purpose are derived the same way, so a seeded
        # item is indistinguishable from a manually-added one until
        # enrich.py (or the modal's per-item refresh) fills in real data.
        items.append(
            {
                "id": uuid.uuid4().hex,
                "name": name,
                "repo": repo,
                "url": f"https://github.com/{repo}" if repo else "",
                "stars": 0,
                "function": function,
                "dev_note": _clean_cell(cells[6]),
                "kind": classify_kind(name, function),
                "purpose": classify_purpose(name, function),
                "status": "candidata",
                "personal_note": "",
                "decided_at": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    return items


def import_catalog(md_path: Path, items_path: Path, now=None) -> list[dict]:
    """Seed items.json from md_path unless items_path already exists."""
    if items_path.exists():
        return json.loads(items_path.read_text(encoding="utf-8"))

    md_text = md_path.read_text(encoding="utf-8")
    items = parse_catalog_markdown(md_text)

    items_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = items_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, items_path)
    return items


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("usage: seed.py <catalog.md> <items.json>", file=sys.stderr)
        raise SystemExit(2)
    result = import_catalog(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"seeded {len(result)} items -> {sys.argv[2]}")
