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
<!-- Aplica o tema salvo ANTES do CSS pintar, evitando flash de tema errado. -->
<script>
(function () {{
  try {{
    var t = localStorage.getItem("theme");
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  }} catch (e) {{}}
}})();
</script>
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
const STATUS_LABEL = { candidata: "candidata", aprovada: "aprovada", rejeitada: "rejeitada" };
const EDITABLE = ["name", "repo", "stars", "function", "dev_note"];

let items = [];
let filterStatus = null;
let expanded = new Set(); // ids currently showing the edit form

// ---- tema: claro/escuro/auto, persistido em localStorage -----------------
function currentTheme() {
  try {
    return localStorage.getItem("theme");
  } catch (e) {
    return null;
  }
}

function setTheme(theme) {
  if (theme) {
    document.documentElement.setAttribute("data-theme", theme);
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
  try {
    if (theme) localStorage.setItem("theme", theme);
    else localStorage.removeItem("theme");
  } catch (e) {}
}

function isDark() {
  const explicit = currentTheme();
  if (explicit) return explicit === "dark";
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function renderThemeToggle() {
  const btn = document.createElement("button");
  btn.className = "theme-toggle";
  btn.type = "button";
  btn.title = "alternar tema";
  btn.textContent = isDark() ? "☀" : "☾";
  btn.onclick = () => {
    setTheme(isDark() ? "light" : "dark");
    render();
  };
  return btn;
}

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

// Refreshes state from the backend and re-renders in place — the served
// index.html is a static snapshot regenerated only on the cron/regen loop,
// so a full page reload would show stale data until that runs.
function reload() {
  return call("list", {}).then((data) => {
    items = data.items || [];
    render();
  });
}

function handleError(err, localErrEl) {
  showError(localErrEl, describe(err));
}

function renderTopbar() {
  const bar = document.createElement("div");
  bar.className = "topbar";

  const h1 = document.createElement("h1");
  h1.textContent = "My Skill-Agents Library";
  bar.appendChild(h1);

  const right = document.createElement("div");
  right.className = "topbar-right";
  const count = document.createElement("span");
  count.className = "topbar-info";
  count.textContent = items.length + " item" + (items.length === 1 ? "" : "s");
  right.appendChild(count);
  right.appendChild(renderThemeToggle());
  bar.appendChild(right);

  return bar;
}

function renderFilters() {
  const filters = document.createElement("div");
  filters.className = "filters";
  ["todas"].concat(STATUSES).forEach((s) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = s === "todas" ? "todas" : STATUS_LABEL[s];
    const active = s === "todas" ? filterStatus === null : s === filterStatus;
    btn.className = "btn btn-sm" + (active ? " btn-primary" : "");
    btn.onclick = () => {
      filterStatus = s === "todas" ? null : s;
      render();
    };
    filters.appendChild(btn);
  });
  return filters;
}

function renderAddForm() {
  const form = document.createElement("form");
  form.className = "add-form card";

  const heading = document.createElement("h2");
  heading.textContent = "adicionar item";
  form.appendChild(heading);

  const grid = document.createElement("div");
  grid.className = "add-form-grid";
  form.appendChild(grid);

  const inputs = {};
  EDITABLE.forEach((field) => {
    const label = document.createElement("label");
    label.textContent = field;
    const input = document.createElement("input");
    input.type = "text";
    input.name = field;
    label.appendChild(input);
    grid.appendChild(label);
    inputs[field] = input;
  });

  const err = document.createElement("div");
  err.className = "error";
  form.appendChild(err);

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.className = "btn btn-primary";
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

  app.appendChild(renderTopbar());

  const container = document.createElement("div");
  container.className = "container";

  container.appendChild(renderFilters());
  container.appendChild(renderAddForm());

  const list = document.createElement("div");
  list.className = "grid";
  const visible = items.filter((i) => !filterStatus || i.status === filterStatus);
  if (visible.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "nenhum item aqui";
    list.appendChild(empty);
  } else {
    visible.forEach((item) => list.appendChild(renderItem(item)));
  }
  container.appendChild(list);

  app.appendChild(container);
}

function renderItem(item) {
  const card = document.createElement("div");
  card.className = "card status-" + item.status;

  const head = document.createElement("div");
  head.className = "card-head";
  const name = document.createElement("span");
  name.className = "card-name";
  name.textContent = item.name || "(sem nome)";
  head.appendChild(name);
  const badge = document.createElement("span");
  badge.className = "badge badge-" + item.status;
  badge.textContent = STATUS_LABEL[item.status] || item.status;
  head.appendChild(badge);
  card.appendChild(head);

  const err = document.createElement("div");
  err.className = "error";

  const select = document.createElement("select");
  select.className = "status-select";
  STATUSES.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = STATUS_LABEL[s];
    opt.selected = s === item.status;
    select.appendChild(opt);
  });
  select.onchange = () => {
    showError(err, "");
    call("set_status", { id: item.id, status: select.value }).then(reload, (ex) =>
      handleError(ex, err)
    );
  };

  if (!expanded.has(item.id)) {
    // ---- compact view ----
    const desc = document.createElement("div");
    desc.className = "card-desc";
    desc.textContent = item.function || "";
    card.appendChild(desc);

    const meta = document.createElement("div");
    meta.className = "card-meta";
    meta.textContent = [item.repo, item.stars].filter(Boolean).join(" · ");
    card.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "actions";
    actions.appendChild(select);

    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "btn btn-sm";
    edit.textContent = "editar";
    edit.onclick = () => {
      expanded.add(item.id);
      render();
    };
    actions.appendChild(edit);

    const del = document.createElement("button");
    del.type = "button";
    del.className = "btn btn-sm danger";
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

  // ---- edit view ----
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
  save.type = "button";
  save.className = "btn btn-sm btn-primary";
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

  const close = document.createElement("button");
  close.type = "button";
  close.className = "btn btn-sm";
  close.textContent = "fechar";
  close.onclick = () => {
    expanded.delete(item.id);
    render();
  };
  actions.appendChild(close);

  const del = document.createElement("button");
  del.type = "button";
  del.className = "btn btn-sm danger";
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
/* =====================================================================
   styles.css - My Skill-Agents Library
   Padrao SPS Design System (TIPO 2), o mesmo do my-Harness-Library:
   header branco 56px, fundo #f0f0f0, cards brancos, acento teal #0d9488.

   Tema claro/escuro por tokens CSS. Tres estados:
     :root                      -> paleta clara (padrao)
     @media prefers-color-scheme -> escuro quando o SO pede e o usuario
                                    nao escolheu (guardado por :not([data-theme="light"]))
     :root[data-theme="dark"]   -> escolha explicita no botao do topo
   Nenhuma cor pode existir SO dentro do media query: o toggle precisa
   vencer nos dois sentidos.
====================================================================== */

:root {
  --bg:          #f0f0f0;
  --fg:          #1f2937;
  --surface:     #ffffff;
  --border:      #e5e7eb;
  --muted:       #6b7280;
  --muted-2:     #9ca3af;
  --strong:      #111827;
  --body-txt:    #374151;
  --accent:      #0d9488;
  --accent-soft: #ccfbf1;
  --shadow:      rgba(0, 0, 0, .06);
  --danger:      #b91c1c;
  /* badges por status */
  --c-candidata-bg: #fef3c7; --c-candidata-fg: #a16207;
  --c-aprovada-bg:  #dcfce7; --c-aprovada-fg:  #15803d;
  --c-rejeitada-bg: #fee2e2; --c-rejeitada-fg: #b91c1c;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:          #111827;
    --fg:          #e5e7eb;
    --surface:     #1f2937;
    --border:      #374151;
    --muted:       #9ca3af;
    --muted-2:     #6b7280;
    --strong:      #f9fafb;
    --body-txt:    #d1d5db;
    --accent:      #2dd4bf;
    --accent-soft: #134e4a;
    --shadow:      rgba(0, 0, 0, .4);
    --danger:      #fca5a5;
    --c-candidata-bg: #4a3410; --c-candidata-fg: #fcd34d;
    --c-aprovada-bg:  #14532d; --c-aprovada-fg:  #86efac;
    --c-rejeitada-bg: #5c1f1f; --c-rejeitada-fg: #fca5a5;
  }
}

:root[data-theme="dark"] {
  --bg:          #111827;
  --fg:          #e5e7eb;
  --surface:     #1f2937;
  --border:      #374151;
  --muted:       #9ca3af;
  --muted-2:     #6b7280;
  --strong:      #f9fafb;
  --body-txt:    #d1d5db;
  --accent:      #2dd4bf;
  --accent-soft: #134e4a;
  --shadow:      rgba(0, 0, 0, .4);
  --danger:      #fca5a5;
  --c-candidata-bg: #4a3410; --c-candidata-fg: #fcd34d;
  --c-aprovada-bg:  #14532d; --c-aprovada-fg:  #86efac;
  --c-rejeitada-bg: #5c1f1f; --c-rejeitada-fg: #fca5a5;
}

* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; background: var(--bg); color: var(--fg); }

/* ---- Header fixo de 56px ---- */
.topbar {
  height: 56px;
  background: var(--surface);
  border-bottom: 3px solid var(--accent);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .75rem;
  padding: 0 1.25rem;
  position: sticky;
  top: 0;
  z-index: 10;
}
.topbar h1 { font-size: 1.05rem; margin: 0; color: var(--accent); }
.topbar-right { display: flex; align-items: center; gap: .75rem; }
.topbar-info { font-size: .78rem; color: var(--muted); }

.theme-toggle {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--muted);
  cursor: pointer;
  font-size: 1rem;
}
.theme-toggle:hover { color: var(--accent); border-color: var(--accent); }

.container { max-width: 1100px; margin: 0 auto; padding: 1.25rem 1rem 3rem; }

/* ---- Filtros ---- */
.filters { display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: 1rem; }

/* ---- Form de adicao ---- */
.add-form { margin-bottom: 1.25rem; }
.add-form h2 { font-size: 1rem; margin: 0 0 .7rem; color: var(--strong); }
.add-form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .7rem; margin-bottom: .7rem; }

label { display: block; font-size: .78rem; color: var(--muted); margin-bottom: .6rem; }
label input, label select {
  display: block;
  width: 100%;
  margin-top: .25rem;
  padding: .4rem .55rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--fg);
  font-size: .85rem;
}

/* ---- Grade de cards ---- */
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; align-items: start; }
.card {
  background: var(--surface);
  border-radius: 8px;
  padding: .85rem 1rem;
  border-left: 4px solid var(--border);
  box-shadow: 0 1px 2px var(--shadow);
}
.card.status-candidata { border-left-color: var(--c-candidata-fg); }
.card.status-aprovada  { border-left-color: var(--c-aprovada-fg); }
.card.status-rejeitada { border-left-color: var(--c-rejeitada-fg); }

.card-head { display: flex; justify-content: space-between; align-items: center; gap: .5rem; margin-bottom: .4rem; }
.card-name { font-weight: 600; font-size: .92rem; color: var(--strong); word-break: break-word; }
.card-desc {
  font-size: .82rem;
  line-height: 1.4;
  color: var(--body-txt);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-meta { margin-top: .35rem; font-size: .72rem; color: var(--muted-2); word-break: break-word; }
.status-select {
  padding: .3rem .45rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--fg);
  font-size: .78rem;
}

.card textarea {
  width: 100%;
  min-height: 3rem;
  margin-top: .3rem;
  padding: .4rem .55rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--fg);
  font-size: .82rem;
  font-family: inherit;
}

/* ---- Badges de status ---- */
.badge { flex-shrink: 0; font-size: .68rem; font-weight: 600; padding: .18rem .55rem; border-radius: 99px; }
.badge-candidata { background: var(--c-candidata-bg); color: var(--c-candidata-fg); }
.badge-aprovada  { background: var(--c-aprovada-bg);  color: var(--c-aprovada-fg); }
.badge-rejeitada { background: var(--c-rejeitada-bg); color: var(--c-rejeitada-fg); }

/* ---- Botoes ---- */
.btn {
  padding: .4rem .9rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--body-txt);
  font-size: .82rem;
  cursor: pointer;
}
.btn:hover { border-color: var(--accent); color: var(--accent); }
.btn-primary { background: var(--accent); border-color: var(--accent); color: var(--bg); font-weight: 500; }
.btn-primary:hover { color: var(--bg); opacity: .9; }
.btn-sm { padding: .3rem .7rem; font-size: .78rem; }
.btn.danger { color: var(--danger); }
.btn.danger:hover { border-color: var(--danger); color: var(--danger); }

.actions { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; margin-top: .6rem; }
.error { color: var(--danger); font-size: .8rem; min-height: 1rem; margin-top: .3rem; }
.empty { text-align: center; color: var(--muted); padding: 2rem 0; grid-column: 1 / -1; }
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
