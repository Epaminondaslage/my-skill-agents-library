#!/usr/bin/env python3
# =============================================================================
# generator.py — renders ~/.claude/.skill-library/items.json into a static
# 3-file site (index.html / app.js / styles.css). Read-only over items.json;
# all mutation happens through api.py.
# =============================================================================

from __future__ import annotations

import json
import os
from pathlib import Path

HOME = Path(os.environ.get("HOME", "")).expanduser()
CLAUDE = HOME / ".claude"
STATE = CLAUDE / ".skill-library"
ITEMS_FILE = STATE / "items.json"
OUT_DIR = Path("/var/www/html/my-skill-agents-library")


def _json_for_script_tag(items: list[dict]) -> str:
    # Standard escape so a payload containing "</script>" cannot break out
    # of the embedding <script> tag.
    return json.dumps(items, ensure_ascii=False).replace("</", "<\\/")


def render_index_html(items: list[dict]) -> str:
    payload = _json_for_script_tag(items)
    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>My Skill-Agents Library</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<div id="app"></div>
<script id="items-data" type="application/json">{payload}</script>
<script src="app.js"></script>
</body>
</html>
"""


def render_app_js() -> str:
    return """\
const API = "/skill-library/api";
const STATUSES = ["candidata", "aprovada", "rejeitada"];

function loadItems() {
  const raw = document.getElementById("items-data").textContent;
  return JSON.parse(raw);
}

function call(action, body) {
  return fetch(API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, ...body }),
  }).then((r) => r.json());
}

function render(items, filterStatus) {
  const app = document.getElementById("app");
  app.innerHTML = "";

  const filters = document.createElement("div");
  filters.className = "filters";
  ["todas", ...STATUSES].forEach((s) => {
    const btn = document.createElement("button");
    btn.textContent = s;
    btn.className = s === filterStatus ? "active" : "";
    btn.onclick = () => render(items, s === "todas" ? null : s);
    filters.appendChild(btn);
  });
  app.appendChild(filters);

  const list = document.createElement("div");
  list.className = "list";
  items
    .filter((i) => !filterStatus || i.status === filterStatus)
    .forEach((item) => list.appendChild(renderItem(item, items)));
  app.appendChild(list);
}

function renderItem(item, items) {
  const card = document.createElement("div");
  card.className = "card status-" + item.status;

  const title = document.createElement("h3");
  title.textContent = item.name + " — " + item.repo;
  card.appendChild(title);

  const fn = document.createElement("p");
  fn.textContent = item.function;
  card.appendChild(fn);

  const select = document.createElement("select");
  STATUSES.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    opt.selected = s === item.status;
    select.appendChild(opt);
  });
  select.onchange = () =>
    call("set_status", { id: item.id, status: select.value }).then(() =>
      window.location.reload()
    );
  card.appendChild(select);

  const note = document.createElement("textarea");
  note.placeholder = "nota pessoal";
  note.value = item.personal_note || "";
  note.onblur = () => call("set_note", { id: item.id, personal_note: note.value });
  card.appendChild(note);

  return card;
}

document.addEventListener("DOMContentLoaded", () => {
  render(loadItems(), null);
});
"""


def render_styles_css() -> str:
    return """\
:root { color-scheme: light dark; }
body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem; }
.filters button { margin-right: .5rem; }
.filters button.active { font-weight: bold; }
.list { display: grid; gap: 1rem; margin-top: 1rem; }
.card { border: 1px solid #8888; border-radius: 8px; padding: .75rem; }
.card textarea { width: 100%; min-height: 3rem; margin-top: .5rem; }
"""


def build_site(items_path: Path, out_dir: Path = OUT_DIR) -> None:
    items = json.loads(items_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(render_index_html(items), encoding="utf-8")
    (out_dir / "app.js").write_text(render_app_js(), encoding="utf-8")
    (out_dir / "styles.css").write_text(render_styles_css(), encoding="utf-8")


if __name__ == "__main__":
    build_site(ITEMS_FILE)
