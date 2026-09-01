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

function renderItem(item) {
  const card = document.createElement("div");
  card.className = "card editable status-" + item.status;
  card.tabIndex = 0;

  const openModal = () => {
    openModalId = item.id;
    render();
  };
  // Any click on the card opens the modal, except on the status select
  // itself — that stays a fast inline action.
  card.onclick = (e) => {
    if (e.target.closest("select")) return;
    openModal();
  };
  card.onkeydown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openModal();
    }
  };

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
  const kindBadge = document.createElement("span");
  kindBadge.className = "badge badge-kind";
  kindBadge.textContent = KIND_LABEL[item.kind] || item.kind;
  head.appendChild(kindBadge);
  const purposeBadge = document.createElement("span");
  purposeBadge.className = "badge badge-" + item.purpose;
  purposeBadge.textContent = PURPOSE_LABEL[item.purpose] || item.purpose;
  head.appendChild(purposeBadge);
  card.appendChild(head);

  const desc = document.createElement("div");
  desc.className = "card-desc";
  desc.textContent = item.function || "";
  card.appendChild(desc);

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

  const actions = document.createElement("div");
  actions.className = "actions";

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
    call("set_status", { id: item.id, status: select.value }).then(reload);
  };
  actions.appendChild(select);
  card.appendChild(actions);

  return card;
}

// Modal shows every field for one item, all editable, plus status/delete.
function renderModal(item) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.onclick = (e) => {
    if (e.target === overlay) closeModal();
  };

  const modal = document.createElement("div");
  modal.className = "modal";
  overlay.appendChild(modal);

  const header = document.createElement("div");
  header.className = "modal-header";
  const title = document.createElement("h2");
  title.textContent = item.name || "(sem nome)";
  header.appendChild(title);
  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "modal-close";
  closeBtn.textContent = "✕";
  closeBtn.onclick = closeModal;
  header.appendChild(closeBtn);
  modal.appendChild(header);

  const body = document.createElement("div");
  body.className = "modal-body";
  modal.appendChild(body);

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
    body.appendChild(label);
    fields[field] = input;
  });

  const statusLabel = document.createElement("label");
  statusLabel.textContent = "status";
  const select = document.createElement("select");
  STATUSES.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = STATUS_LABEL[s];
    opt.selected = s === item.status;
    select.appendChild(opt);
  });
  statusLabel.appendChild(select);
  body.appendChild(statusLabel);

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

  const noteLabel = document.createElement("label");
  noteLabel.textContent = "nota pessoal";
  const note = document.createElement("textarea");
  note.value = item.personal_note || "";
  noteLabel.appendChild(note);
  body.appendChild(noteLabel);

  body.appendChild(err);

  const actions = document.createElement("div");
  actions.className = "actions";
  modal.appendChild(actions);

  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn btn-sm btn-primary";
  save.textContent = "salvar";
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
  actions.appendChild(save);

  const del = document.createElement("button");
  del.type = "button";
  del.className = "btn btn-sm danger";
  del.textContent = "excluir";
  del.onclick = () => {
    if (!window.confirm("excluir \\"" + item.name + "\\"?")) return;
    showError(err, "");
    call("delete", { id: item.id }).then(() => {
      closeModal();
      reload();
    }, (ex) => handleError(ex, err));
  };
  actions.appendChild(del);

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

  return overlay;
}

function closeModal() {
  openModalId = null;
  render();
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && openModalId !== null) closeModal();
});

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
  /* badges por purpose */
  --c-general-bg:      #e5e7eb; --c-general-fg:      #4b5563;
  --c-devops-bg:       #dcfce7; --c-devops-fg:        #15803d;
  --c-spec-ops-bg:     #e0e7ff; --c-spec-ops-fg:      #4338ca;
  --c-quality-bg:      #cffafe; --c-quality-fg:       #0e7490;
  --c-security-bg:     #fee2e2; --c-security-fg:      #b91c1c;
  --c-integrations-bg: #fef3c7; --c-integrations-fg:  #a16207;
  --c-tooling-bg:      #f3e8ff; --c-tooling-fg:       #7e22ce;
  --c-frontend-bg:     #fce7f3; --c-frontend-fg:      #be185d;
  --c-other-bg:        #f3f4f6; --c-other-fg:         #6b7280;
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
    --c-general-bg:      #374151; --c-general-fg:      #d1d5db;
    --c-devops-bg:       #14532d; --c-devops-fg:       #86efac;
    --c-spec-ops-bg:     #312e81; --c-spec-ops-fg:     #a5b4fc;
    --c-quality-bg:      #164e63; --c-quality-fg:      #67e8f9;
    --c-security-bg:     #5c1f1f; --c-security-fg:     #fca5a5;
    --c-integrations-bg: #4a3410; --c-integrations-fg: #fcd34d;
    --c-tooling-bg:      #4a1d6b; --c-tooling-fg:      #d8b4fe;
    --c-frontend-bg:     #61123b; --c-frontend-fg:     #f9a8d4;
    --c-other-bg:        #2d3748; --c-other-fg:        #9ca3af;
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
  --c-general-bg:      #374151; --c-general-fg:      #d1d5db;
  --c-devops-bg:       #14532d; --c-devops-fg:       #86efac;
  --c-spec-ops-bg:     #312e81; --c-spec-ops-fg:     #a5b4fc;
  --c-quality-bg:      #164e63; --c-quality-fg:      #67e8f9;
  --c-security-bg:     #5c1f1f; --c-security-fg:     #fca5a5;
  --c-integrations-bg: #4a3410; --c-integrations-fg: #fcd34d;
  --c-tooling-bg:      #4a1d6b; --c-tooling-fg:      #d8b4fe;
  --c-frontend-bg:     #61123b; --c-frontend-fg:     #f9a8d4;
  --c-other-bg:        #2d3748; --c-other-fg:        #9ca3af;
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

.card.editable { cursor: pointer; transition: box-shadow .12s, transform .12s; }
.card.editable:hover { box-shadow: 0 3px 10px var(--shadow); transform: translateY(-1px); }
.card.editable:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

/* ---- Modal (todos os dados de um item) ---- */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, .45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 100;
}
.modal {
  background: var(--surface);
  border-radius: 10px;
  box-shadow: 0 10px 30px var(--shadow);
  width: min(480px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  padding: 1rem 1.25rem 1.25rem;
}
.modal-header { display: flex; justify-content: space-between; align-items: center; gap: .75rem; margin-bottom: .8rem; }
.modal-header h2 { font-size: 1.05rem; margin: 0; color: var(--strong); word-break: break-word; }
.modal-close {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--muted);
  cursor: pointer;
}
.modal-close:hover { color: var(--danger); border-color: var(--danger); }
.modal label { margin-bottom: .7rem; }

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
