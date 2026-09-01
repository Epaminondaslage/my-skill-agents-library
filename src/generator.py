#!/usr/bin/env python3
# =============================================================================
# generator.py — renders ~/.claude/.skill-library/items.json into a static
# 3-file site (index.html / app.js / styles.css). Read-only over items.json;
# all mutation happens through api.py.
# =============================================================================

from __future__ import annotations

import json
import os
import sys
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
    # Every node is built with createElement/textContent — never innerHTML —
    # so item text can never be interpreted as markup.
    return """\
const API = "/skill-library/api";
const STATUSES = ["candidata", "aprovada", "rejeitada"];
const EDITABLE = ["name", "repo", "stars", "function", "dev_note"];

let items = [];
let filterStatus = null;

function loadItems() {
  const raw = document.getElementById("items-data").textContent;
  return JSON.parse(raw);
}

function showError(el, message) {
  if (el) el.textContent = message || "";
}

// Resolves with the parsed payload, or rejects with an Error carrying the
// backend's message so callers can surface it.
function call(action, body) {
  const payload = { action: action };
  Object.keys(body || {}).forEach((k) => {
    payload[k] = body[k];
  });
  return fetch(API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) =>
    r.json().then((data) => {
      if (!r.ok || (data && data.error)) {
        const err = new Error((data && data.error) || "erro " + r.status);
        err.code = data && data.code;
        err.status = r.status;
        throw err;
      }
      return data;
    })
  );
}

function describe(err) {
  return (err && err.message) || "falha na comunicação com o servidor";
}

function reload() {
  window.location.reload();
}

function handleError(err, localErrEl) {
  showError(localErrEl, describe(err));
}

function renderAddForm() {
  const form = document.createElement("form");
  form.className = "add-form";

  const heading = document.createElement("h2");
  heading.textContent = "adicionar item";
  form.appendChild(heading);

  const inputs = {};
  EDITABLE.forEach((field) => {
    const label = document.createElement("label");
    label.textContent = field;
    const input = document.createElement("input");
    input.type = "text";
    input.name = field;
    label.appendChild(input);
    form.appendChild(label);
    inputs[field] = input;
  });

  const err = document.createElement("div");
  err.className = "error";
  form.appendChild(err);

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = "adicionar";
  form.appendChild(submit);

  form.onsubmit = (e) => {
    e.preventDefault();
    showError(err, "");
    const body = {};
    EDITABLE.forEach((f) => {
      body[f] = inputs[f].value;
    });
    call("add", body).then(reload, (ex) => handleError(ex, err));
  };
  return form;
}

function render() {
  const app = document.getElementById("app");
  while (app.firstChild) app.removeChild(app.firstChild);


  const filters = document.createElement("div");
  filters.className = "filters";
  ["todas"].concat(STATUSES).forEach((s) => {
    const btn = document.createElement("button");
    btn.textContent = s;
    const active = s === "todas" ? filterStatus === null : s === filterStatus;
    btn.className = active ? "active" : "";
    btn.onclick = () => {
      filterStatus = s === "todas" ? null : s;
      render();
    };
    filters.appendChild(btn);
  });
  app.appendChild(filters);

  app.appendChild(renderAddForm());

  const list = document.createElement("div");
  list.className = "list";
  items
    .filter((i) => !filterStatus || i.status === filterStatus)
    .forEach((item) => list.appendChild(renderItem(item)));
  app.appendChild(list);
}

function renderItem(item) {
  const card = document.createElement("div");
  card.className = "card status-" + item.status;

  const err = document.createElement("div");
  err.className = "error";

  const fields = {};
  EDITABLE.forEach((field) => {
    const label = document.createElement("label");
    label.textContent = field;
    const input = document.createElement("input");
    input.type = "text";
    input.value = item[field] || "";
    label.appendChild(input);
    card.appendChild(label);
    fields[field] = input;
  });

  const select = document.createElement("select");
  STATUSES.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    opt.selected = s === item.status;
    select.appendChild(opt);
  });
  select.onchange = () => {
    showError(err, "");
    call("set_status", { id: item.id, status: select.value }).then(reload, (ex) =>
      handleError(ex, err)
    );
  };
  card.appendChild(select);

  const note = document.createElement("textarea");
  note.placeholder = "nota pessoal";
  note.value = item.personal_note || "";
  note.onblur = () => {
    if (note.value === (item.personal_note || "")) return;
    showError(err, "");
    call("set_note", { id: item.id, personal_note: note.value }).then((updated) => {
      item.personal_note = updated.personal_note;
    }, (ex) => handleError(ex, err));
  };
  card.appendChild(note);

  const actions = document.createElement("div");
  actions.className = "actions";

  const save = document.createElement("button");
  save.textContent = "salvar";
  save.onclick = () => {
    showError(err, "");
    const body = { id: item.id };
    EDITABLE.forEach((f) => {
      body[f] = fields[f].value;
    });
    call("edit", body).then(reload, (ex) => handleError(ex, err));
  };
  actions.appendChild(save);

  const del = document.createElement("button");
  del.className = "danger";
  del.textContent = "excluir";
  del.onclick = () => {
    if (!window.confirm("excluir \\"" + item.name + "\\"?")) return;
    showError(err, "");
    call("delete", { id: item.id }).then(reload, (ex) => handleError(ex, err));
  };
  actions.appendChild(del);

  card.appendChild(actions);
  card.appendChild(err);
  return card;
}

document.addEventListener("DOMContentLoaded", () => {
  items = loadItems();
  render();
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
.add-form { border: 1px dashed #8888; border-radius: 8px; padding: .75rem; margin-top: 1rem; }
.add-form h2 { font-size: 1rem; margin: 0 0 .5rem; }
label { display: block; margin-bottom: .4rem; font-size: .8rem; }
label input { display: block; width: 100%; }
.actions { display: flex; gap: .5rem; margin-top: .5rem; }
.actions .danger { color: #b00; }
.error { color: #b00; font-size: .85rem; min-height: 1rem; }
"""


def build_site(items_path: Path, out_dir: Path = OUT_DIR) -> None:
    # A missing items.json is the normal first-run state (no catalog markdown
    # to seed from yet): start empty and warn. A *corrupt* items.json is a
    # different matter — that still raises, so a parse error is never mistaken
    # for "the library is empty" and published as such.
    if items_path.exists():
        items = json.loads(items_path.read_text(encoding="utf-8"))
    else:
        print(
            f"warning: {items_path} not found — generating an empty site. "
            "Seed it from Catalogo-de-Agent-Skills.md, or add items from the page.",
            file=sys.stderr,
        )
        items = []
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(render_index_html(items), encoding="utf-8")
    (out_dir / "app.js").write_text(render_app_js(), encoding="utf-8")
    (out_dir / "styles.css").write_text(render_styles_css(), encoding="utf-8")


if __name__ == "__main__":
    build_site(ITEMS_FILE)
