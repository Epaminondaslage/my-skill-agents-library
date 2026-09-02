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
const KINDS = ["skill", "agent", "command", "plugin", "mcp"];
const PURPOSES = [
  "general", "devops", "spec-ops", "quality", "security",
  "integrations", "tooling", "frontend", "other",
];
const SORTS = ["default", "stars", "updated", "name"];
const EDITABLE = ["name", "repo", "function", "dev_note"];

// ---- i18n: pt (default) / en / es, persisted in localStorage --------------
// Item DATA (name/function/dev_note/personal_note) is never translated —
// only the UI chrome below is. STRINGS falls back to pt for any missing key.
const LANGS = ["pt", "en", "es"];
const LANG_FLAG = { pt: "🇧🇷", en: "🇺🇸", es: "🇪🇸" };
const STRINGS = {
  pt: {
    subtitle: "Catálogo de skills, agents, commands, MCPs e plugins para acelerar o ciclo de desenvolvimento de software",
    itemsCount: (n) => n + " item" + (n === 1 ? "" : "s"),
    themeToggleTitle: "alternar tema",
    langToggleTitle: "mudar idioma",
    searchPlaceholder: "buscar por nome, repo ou função...",
    ghSearchTitle: "buscar repositórios no GitHub",
    addToCatalog: "+ incluir no catálogo",
    ghSearching: "buscando no GitHub…",
    ghResultsTitle: "resultados do GitHub",
    ghNoResults: "nenhum repositório encontrado",
    ghResultsFound: (n) => n + " repositório" + (n === 1 ? "" : "s") + " encontrado" + (n === 1 ? "" : "s"),
    ghErrorGeneric: "erro na busca do GitHub",
    ghErrorFetch: "falha ao consultar a API do GitHub",
    ghCloseTitle: "fechar resultados",
    ghAlreadyAdded: "já no catálogo",
    ghInclude: "+ incluir",
    ghIncluding: "incluindo…",
    filterAll: "todas",
    kindFilterAll: "Todos",
    purposeFilterAll: "Todos",
    addItemHeading: "adicionar item",
    addSubmit: "adicionar",
    noName: "(sem nome)",
    emptySection: "nenhum item aqui",
    modalStatus: "status",
    modalKind: "kind",
    modalPurpose: "purpose",
    modalNote: "nota pessoal",
    save: "salvar",
    delete: "excluir",
    refreshGithub: "atualizar do GitHub",
    confirmDelete: (name) => 'excluir "' + name + '"?',
    errNoServer: "falha na comunicação com o servidor",
    errGeneric: (status) => "erro " + status,
    status: { candidata: "candidata", aprovada: "aprovada", rejeitada: "rejeitada" },
    kind: { skill: "Skills", agent: "Agents", command: "Commands", plugin: "Plugins", mcp: "MCPs" },
    purpose: {
      general: "General", devops: "DevOps", "spec-ops": "Spec-Driven Ops", quality: "Quality",
      security: "Security", integrations: "Integrations", tooling: "Tooling",
      frontend: "Frontend", other: "Other",
    },
    sort: { default: "Padrão", stars: "Mais estrelas", updated: "Atualização recente", name: "Nome" },
  },
  en: {
    subtitle: "Catalog of skills, agents, commands, MCPs, and plugins to speed up the software development cycle",
    itemsCount: (n) => n + " item" + (n === 1 ? "" : "s"),
    themeToggleTitle: "toggle theme",
    langToggleTitle: "change language",
    searchPlaceholder: "search by name, repo, or function...",
    ghSearchTitle: "search repositories on GitHub",
    addToCatalog: "+ add to catalog",
    ghSearching: "searching GitHub…",
    ghResultsTitle: "GitHub results",
    ghNoResults: "no repositories found",
    ghResultsFound: (n) => n + " repositor" + (n === 1 ? "y" : "ies") + " found",
    ghErrorGeneric: "error searching GitHub",
    ghErrorFetch: "failed to reach the GitHub API",
    ghCloseTitle: "close results",
    ghAlreadyAdded: "already in catalog",
    ghInclude: "+ add",
    ghIncluding: "adding…",
    filterAll: "all",
    kindFilterAll: "All",
    purposeFilterAll: "All",
    addItemHeading: "add item",
    addSubmit: "add",
    noName: "(no name)",
    emptySection: "nothing here",
    modalStatus: "status",
    modalKind: "kind",
    modalPurpose: "purpose",
    modalNote: "personal note",
    save: "save",
    delete: "delete",
    refreshGithub: "refresh from GitHub",
    confirmDelete: (name) => 'delete "' + name + '"?',
    errNoServer: "failed to communicate with the server",
    errGeneric: (status) => "error " + status,
    status: { candidata: "candidate", aprovada: "approved", rejeitada: "rejected" },
    kind: { skill: "Skills", agent: "Agents", command: "Commands", plugin: "Plugins", mcp: "MCPs" },
    purpose: {
      general: "General", devops: "DevOps", "spec-ops": "Spec-Driven Ops", quality: "Quality",
      security: "Security", integrations: "Integrations", tooling: "Tooling",
      frontend: "Frontend", other: "Other",
    },
    sort: { default: "Default", stars: "Most stars", updated: "Recently updated", name: "Name" },
  },
  es: {
    subtitle: "Catálogo de skills, agents, commands, MCPs y plugins para acelerar el ciclo de desarrollo de software",
    itemsCount: (n) => n + " elemento" + (n === 1 ? "" : "s"),
    themeToggleTitle: "cambiar tema",
    langToggleTitle: "cambiar idioma",
    searchPlaceholder: "buscar por nombre, repo o función...",
    ghSearchTitle: "buscar repositorios en GitHub",
    addToCatalog: "+ incluir en el catálogo",
    ghSearching: "buscando en GitHub…",
    ghResultsTitle: "resultados de GitHub",
    ghNoResults: "no se encontraron repositorios",
    ghResultsFound: (n) => n + " repositorio" + (n === 1 ? "" : "s") + " encontrado" + (n === 1 ? "" : "s"),
    ghErrorGeneric: "error en la búsqueda de GitHub",
    ghErrorFetch: "fallo al consultar la API de GitHub",
    ghCloseTitle: "cerrar resultados",
    ghAlreadyAdded: "ya en el catálogo",
    ghInclude: "+ incluir",
    ghIncluding: "incluyendo…",
    filterAll: "todas",
    kindFilterAll: "Todos",
    purposeFilterAll: "Todos",
    addItemHeading: "añadir elemento",
    addSubmit: "añadir",
    noName: "(sin nombre)",
    emptySection: "nada aquí",
    modalStatus: "status",
    modalKind: "kind",
    modalPurpose: "purpose",
    modalNote: "nota personal",
    save: "guardar",
    delete: "eliminar",
    refreshGithub: "actualizar desde GitHub",
    confirmDelete: (name) => '¿eliminar "' + name + '"?',
    errNoServer: "fallo en la comunicación con el servidor",
    errGeneric: (status) => "error " + status,
    status: { candidata: "candidata", aprovada: "aprobada", rejeitada: "rechazada" },
    kind: { skill: "Skills", agent: "Agents", command: "Commands", plugin: "Plugins", mcp: "MCPs" },
    purpose: {
      general: "General", devops: "DevOps", "spec-ops": "Spec-Driven Ops", quality: "Quality",
      security: "Security", integrations: "Integrations", tooling: "Tooling",
      frontend: "Frontend", other: "Other",
    },
    sort: { default: "Predeterminado", stars: "Más estrellas", updated: "Actualización reciente", name: "Nombre" },
  },
};

function currentLang() {
  try {
    const l = localStorage.getItem("lang");
    return LANGS.indexOf(l) !== -1 ? l : "pt";
  } catch (e) {
    return "pt";
  }
}

function setLang(l) {
  lang = l;
  try {
    localStorage.setItem("lang", l);
  } catch (e) {}
}

// t(key) resolves a UI string in the current language, falling back to pt.
function t(key) {
  const v = (STRINGS[lang] && STRINGS[lang][key] !== undefined) ? STRINGS[lang][key] : STRINGS.pt[key];
  return v;
}
function statusLabel(s) { return (STRINGS[lang].status && STRINGS[lang].status[s]) || STRINGS.pt.status[s] || s; }
function kindLabel(k) { return (STRINGS[lang].kind && STRINGS[lang].kind[k]) || STRINGS.pt.kind[k] || k; }
function purposeLabel(p) { return (STRINGS[lang].purpose && STRINGS[lang].purpose[p]) || STRINGS.pt.purpose[p] || p; }
function sortLabel(s) { return (STRINGS[lang].sort && STRINGS[lang].sort[s]) || STRINGS.pt.sort[s] || s; }

let lang = currentLang();
let items = [];
let filterStatus = null;
let filterKind = null;
let filterPurpose = null;
let searchQuery = "";
let ghResults = null; // null = no search done yet, [] = no matches, array = results
let ghLoading = false;
let ghError = "";
let ghAddedRepos = {}; // full_name -> true, for "already added" state after a quick-add
let sortBy = "default";
let openModalId = null; // id of the item whose modal is open, or null
let addModalOpen = false; // whether the "adicionar item" modal is open
let addModalPrefillName = ""; // name to prefill when opening it from a search

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
  btn.title = t("themeToggleTitle");
  btn.textContent = isDark() ? "☀" : "☾";
  btn.onclick = () => {
    setTheme(isDark() ? "light" : "dark");
    render();
  };
  return btn;
}

function renderLangToggle() {
  const btn = document.createElement("button");
  btn.className = "theme-toggle lang-toggle";
  btn.type = "button";
  btn.title = t("langToggleTitle");
  btn.textContent = LANG_FLAG[lang];
  btn.onclick = () => {
    setLang(LANGS[(LANGS.indexOf(lang) + 1) % LANGS.length]);
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
        const err = new Error((data && data.error) || t("errGeneric")(r.status));
        err.code = data && data.code;
        err.status = r.status;
        throw err;
      }
      return data;
    })
  );
}

function describe(err) {
  return (err && err.message) || t("errNoServer");
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

  const titleGroup = document.createElement("div");
  titleGroup.className = "topbar-title-group";
  const h1 = document.createElement("h1");
  h1.textContent = "My Skill-Agents Library";
  titleGroup.appendChild(h1);
  const subtitle = document.createElement("span");
  subtitle.className = "topbar-subtitle";
  subtitle.textContent = t("subtitle");
  titleGroup.appendChild(subtitle);
  bar.appendChild(titleGroup);

  const right = document.createElement("div");
  right.className = "topbar-right";
  const count = document.createElement("span");
  count.className = "topbar-info";
  count.textContent = t("itemsCount")(items.length);
  right.appendChild(count);
  right.appendChild(renderLangToggle());
  right.appendChild(renderThemeToggle());
  bar.appendChild(right);

  return bar;
}

const GITHUB_MARK_SVG =
  '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true">' +
  '<path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 ' +
  '0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c' +
  '-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998' +
  '.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22' +
  '-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 ' +
  '2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 ' +
  '1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 ' +
  '0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>';

function renderSearchBox() {
  const wrap = document.createElement("div");
  wrap.className = "search-box";
  const field = document.createElement("div");
  field.className = "search-field";
  const icon = document.createElement("span");
  icon.className = "search-icon";
  icon.textContent = "🔍";
  icon.setAttribute("aria-hidden", "true");
  const input = document.createElement("input");
  input.type = "search";
  input.className = "search-input";
  input.placeholder = t("searchPlaceholder");
  input.value = searchQuery;
  input.oninput = (e) => {
    searchQuery = e.target.value;
    render();
  };
  field.appendChild(icon);
  field.appendChild(input);
  wrap.appendChild(field);

  const actions = document.createElement("div");
  actions.className = "search-actions";

  const ghBtn = document.createElement("button");
  ghBtn.type = "button";
  ghBtn.className = "btn btn-sm search-gh-btn";
  ghBtn.title = t("ghSearchTitle");
  ghBtn.innerHTML = GITHUB_MARK_SVG;
  ghBtn.disabled = ghLoading;
  ghBtn.onclick = () => searchGithub();
  actions.appendChild(ghBtn);

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "btn btn-sm search-add-btn";
  addBtn.textContent = t("addToCatalog");
  addBtn.onclick = () => openAddModal(searchQuery.trim());
  actions.appendChild(addBtn);

  const newItemBtn = document.createElement("button");
  newItemBtn.type = "button";
  newItemBtn.className = "btn btn-sm search-newitem-btn";
  newItemBtn.textContent = t("addItemHeading");
  newItemBtn.onclick = () => openAddModal("");
  actions.appendChild(newItemBtn);

  wrap.appendChild(actions);
  return wrap;
}

function openAddModal(prefillName) {
  addModalOpen = true;
  addModalPrefillName = prefillName || "";
  render();
  const nameInput = document.getElementById("add-field-name");
  if (nameInput) nameInput.focus();
}

function closeAddModal() {
  addModalOpen = false;
  addModalPrefillName = "";
  render();
}

// Live GitHub repo search (github.com/search only filters the catalog we
// already store — this hits GitHub's public search API from the browser
// so results carry a real description, url and star count). Unauthenticated,
// so it's rate-limited to 10 req/min — fine for interactive manual use.
function searchGithub() {
  const q = searchQuery.trim();
  if (!q) return;
  ghLoading = true;
  ghError = "";
  render();
  fetch("https://api.github.com/search/repositories?q=" + encodeURIComponent(q) + "&sort=stars&order=desc&per_page=8", {
    headers: { Accept: "application/vnd.github+json" },
  })
    .then((r) => r.json().then((data) => ({ ok: r.ok, data })))
    .then(({ ok, data }) => {
      ghLoading = false;
      if (!ok) {
        ghError = (data && data.message) || t("ghErrorGeneric");
        ghResults = null;
      } else {
        ghResults = data.items || [];
      }
      render();
    })
    .catch(() => {
      ghLoading = false;
      ghError = t("ghErrorFetch");
      ghResults = null;
      render();
    });
}

function renderGithubResultsHeader(labelText) {
  const header = document.createElement("div");
  header.className = "gh-results-header";
  const label = document.createElement("span");
  label.textContent = labelText;
  header.appendChild(label);
  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "gh-results-close";
  closeBtn.title = t("ghCloseTitle");
  closeBtn.setAttribute("aria-label", t("ghCloseTitle"));
  closeBtn.textContent = "✕";
  closeBtn.onclick = () => {
    ghResults = null;
    ghError = "";
    render();
  };
  header.appendChild(closeBtn);
  return header;
}

function renderGithubResults() {
  if (!ghLoading && !ghError && ghResults === null) return null;
  const box = document.createElement("div");
  box.className = "gh-results card";

  if (ghLoading) {
    box.appendChild(renderGithubResultsHeader(t("ghSearching")));
    return box;
  }
  if (ghError) {
    box.appendChild(renderGithubResultsHeader(t("ghResultsTitle")));
    const p = document.createElement("div");
    p.className = "gh-results-status error";
    p.textContent = ghError;
    box.appendChild(p);
    return box;
  }

  box.appendChild(renderGithubResultsHeader(
    ghResults.length === 0 ? t("ghNoResults") : t("ghResultsFound")(ghResults.length)
  ));
  if (ghResults.length === 0) return box;

  const knownRepos = {};
  items.forEach((i) => {
    if (i.repo) knownRepos[i.repo.toLowerCase()] = true;
  });

  ghResults.forEach((repo) => {
    const wrap = document.createElement("div");
    wrap.className = "gh-result";

    const row = document.createElement("div");
    row.className = "gh-result-row";

    const main = document.createElement("div");
    main.className = "gh-result-main";

    const link = document.createElement("a");
    link.href = repo.html_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.className = "gh-result-name";
    link.textContent = repo.full_name;
    main.appendChild(link);

    if (repo.description) {
      const desc = document.createElement("div");
      desc.className = "gh-result-desc";
      desc.textContent = repo.description;
      main.appendChild(desc);
    }
    row.appendChild(main);

    const stars = renderStars(repo.stargazers_count);
    stars.classList.add("gh-result-stars");
    row.appendChild(stars);

    const already = !!knownRepos[(repo.full_name || "").toLowerCase()] || !!ghAddedRepos[repo.full_name];
    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "btn btn-sm gh-result-add";
    addBtn.textContent = already ? t("ghAlreadyAdded") : t("ghInclude");
    addBtn.disabled = already;
    row.appendChild(addBtn);

    wrap.appendChild(row);

    const rowErr = document.createElement("div");
    rowErr.className = "error gh-result-error";
    wrap.appendChild(rowErr);

    addBtn.onclick = () => {
      showError(rowErr, "");
      addBtn.disabled = true;
      addBtn.textContent = t("ghIncluding");
      call("add", {
        name: repo.name,
        repo: repo.full_name,
        function: repo.description || "",
        dev_note: "",
      })
        .then(() => {
          ghAddedRepos[repo.full_name] = true;
          reload();
        })
        .catch((ex) => {
          addBtn.disabled = false;
          addBtn.textContent = t("ghInclude");
          showError(rowErr, describe(ex));
        });
    };

    box.appendChild(wrap);
  });

  return box;
}

function renderFilters() {
  return renderPillRow(
    "filters", t("filterAll"), STATUSES, (s) => statusLabel(s), filterStatus,
    (s) => { filterStatus = s; render(); },
    (s) => countBy(items, "status", s),
    (s) => "badge-" + s
  );
}

function sortItems(list) {
  const sorted = list.slice();
  if (sortBy === "stars") sorted.sort((a, b) => (b.stars || 0) - (a.stars || 0));
  else if (sortBy === "updated") sorted.sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
  else if (sortBy === "name") sorted.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
  return sorted;
}

function renderStars(stars) {
  const wrap = document.createElement("span");
  wrap.className = "star";
  const icon = document.createElement("span");
  icon.className = "star-icon";
  icon.textContent = "★";
  const count = document.createElement("span");
  count.className = "star-count";
  count.textContent = String(stars || 0);
  wrap.appendChild(icon);
  wrap.appendChild(document.createTextNode(" "));
  wrap.appendChild(count);
  return wrap;
}

function countBy(list, key, value) {
  return list.filter((i) => (value === null ? true : i[key] === value)).length;
}

function renderPillRow(className, allLabel, options, labelFn, active, onPick, countFn, colorClassFn) {
  const row = document.createElement("div");
  row.className = className;
  const withAll = allLabel === null ? options : [null].concat(options);
  withAll.forEach((opt) => {
    const btn = document.createElement("button");
    btn.type = "button";
    const label = opt === null ? allLabel : labelFn(opt);
    const count = countFn ? countFn(opt) : null;
    btn.textContent = count === null ? label : label + " " + count;
    const colorClass = opt !== null && colorClassFn ? " " + colorClassFn(opt) : "";
    btn.className = "btn btn-sm" + (opt === active ? " btn-primary" : "") + colorClass;
    btn.onclick = () => onPick(opt);
    row.appendChild(btn);
  });
  return row;
}

function renderKindFilter() {
  return renderPillRow(
    "filters", t("kindFilterAll"), KINDS, (k) => kindLabel(k), filterKind,
    (k) => { filterKind = k; render(); },
    (k) => countBy(items, "kind", k)
  );
}

// Purpose keys, in tab order: null (Todos) is "1", then one digit per
// PURPOSES entry. Also used by the global digit-key shortcut handler below.
const PURPOSE_TAB_KEYS = ["1"].concat(PURPOSES.map((_, i) => String(i + 2)));

function purposeTabTarget(key) {
  const idx = PURPOSE_TAB_KEYS.indexOf(key);
  if (idx === -1) return undefined;
  return idx === 0 ? null : PURPOSES[idx - 1];
}

function renderPurposeFilter() {
  const tabs = document.createElement("div");
  tabs.className = "purpose-tabs";
  [null].concat(PURPOSES).forEach((p, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    const label = p === null ? t("purposeFilterAll") : purposeLabel(p);
    const count = countBy(items, "purpose", p);
    const active = p === filterPurpose;
    const colorClass = p !== null ? " pill-purpose-" + p : "";
    btn.className = "purpose-tab" + (active ? " active" : "") + colorClass;
    btn.onclick = () => { filterPurpose = p; render(); };

    const text = document.createElement("span");
    text.textContent = label + " " + count;
    btn.appendChild(text);

    const kbd = document.createElement("kbd");
    kbd.className = "tab-shortcut";
    kbd.textContent = PURPOSE_TAB_KEYS[i];
    btn.appendChild(kbd);

    tabs.appendChild(btn);
  });
  return tabs;
}

function renderSortFilter() {
  return renderPillRow(
    "filters", null, SORTS, (s) => sortLabel(s), sortBy,
    (s) => { sortBy = s || "default"; render(); },
    null
  );
}

function renderAddModal() {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.onclick = (e) => {
    if (e.target === overlay) closeAddModal();
  };

  const modal = document.createElement("div");
  modal.className = "modal";
  overlay.appendChild(modal);

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "modal-close";
  closeBtn.textContent = "✕";
  closeBtn.onclick = closeAddModal;
  modal.appendChild(closeBtn);

  const form = document.createElement("form");
  form.id = "add-form";
  form.className = "add-form";

  const heading = document.createElement("h2");
  heading.textContent = t("addItemHeading");
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
    input.id = "add-field-" + field;
    if (field === "name") input.value = addModalPrefillName;
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
  submit.textContent = t("addSubmit");
  form.appendChild(submit);

  form.onsubmit = (e) => {
    e.preventDefault();
    showError(err, "");
    const body = {};
    EDITABLE.forEach((f) => {
      body[f] = inputs[f].value;
    });
    call("add", body).then(() => {
      closeAddModal();
      reload();
    }, (ex) => handleError(ex, err));
  };
  modal.appendChild(form);
  return overlay;
}

function render() {
  const app = document.getElementById("app");
  const prevFocus = document.activeElement;
  const restoreSearchFocus = prevFocus && prevFocus.classList && prevFocus.classList.contains("search-input");
  const caret = restoreSearchFocus ? prevFocus.selectionStart : null;
  while (app.firstChild) app.removeChild(app.firstChild);

  app.appendChild(renderTopbar());

  const container = document.createElement("div");
  container.className = "container";

  container.appendChild(renderFilters());
  container.appendChild(renderKindFilter());
  container.appendChild(renderPurposeFilter());
  container.appendChild(renderSortFilter());
  container.appendChild(renderSearchBox());
  const ghResultsEl = renderGithubResults();
  if (ghResultsEl) container.appendChild(ghResultsEl);

  const q = searchQuery.trim().toLowerCase();
  const filtered = items.filter(
    (i) =>
      (!filterStatus || i.status === filterStatus) &&
      (!filterKind || i.kind === filterKind) &&
      (!filterPurpose || i.purpose === filterPurpose) &&
      (q === "" ||
        (i.name || "").toLowerCase().includes(q) ||
        (i.repo || "").toLowerCase().includes(q) ||
        (i.function || "").toLowerCase().includes(q))
  );

  container.appendChild(renderSections(filtered));

  app.appendChild(container);

  const openItem = items.find((i) => i.id === openModalId);
  if (openItem) app.appendChild(renderModal(openItem));
  if (addModalOpen) app.appendChild(renderAddModal());

  if (restoreSearchFocus) {
    const newInput = app.querySelector(".search-input");
    if (newInput) {
      newInput.focus();
      try {
        newInput.setSelectionRange(caret, caret);
      } catch (e) {}
    }
  }
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
    head.textContent = purposeLabel(purpose) + " (" + group.length + ")";
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
    empty.textContent = t("emptySection");
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
  name.textContent = item.name || t("noName");
  head.appendChild(name);
  const badge = document.createElement("span");
  badge.className = "badge badge-" + item.status;
  badge.textContent = statusLabel(item.status);
  head.appendChild(badge);
  const kindBadge = document.createElement("span");
  kindBadge.className = "badge badge-kind";
  kindBadge.textContent = kindLabel(item.kind);
  head.appendChild(kindBadge);
  const purposeBadge = document.createElement("span");
  purposeBadge.className = "badge badge-" + item.purpose;
  purposeBadge.textContent = purposeLabel(item.purpose);
  head.appendChild(purposeBadge);
  card.appendChild(head);

  const desc = document.createElement("div");
  desc.className = "card-desc";
  desc.textContent = item.function || "";
  card.appendChild(desc);

  const meta = document.createElement("div");
  meta.className = "card-meta";
  meta.appendChild(renderStars(item.stars));
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
    opt.textContent = statusLabel(s);
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
  title.textContent = item.name || t("noName");
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
    const input = document.createElement(field === "function" ? "textarea" : "input");
    if (field === "function") input.className = "function-field";
    else input.type = "text";
    input.value = item[field] || "";
    label.appendChild(input);
    body.appendChild(label);
    fields[field] = input;
  });

  const statusFieldLabel = document.createElement("label");
  statusFieldLabel.textContent = t("modalStatus");
  const select = document.createElement("select");
  STATUSES.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = statusLabel(s);
    opt.selected = s === item.status;
    select.appendChild(opt);
  });
  statusFieldLabel.appendChild(select);
  body.appendChild(statusFieldLabel);

  const kindFieldLabel = document.createElement("label");
  kindFieldLabel.textContent = t("modalKind");
  const kindSelect = document.createElement("select");
  KINDS.forEach((k) => {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = kindLabel(k);
    opt.selected = k === item.kind;
    kindSelect.appendChild(opt);
  });
  kindFieldLabel.appendChild(kindSelect);
  body.appendChild(kindFieldLabel);

  const purposeFieldLabel = document.createElement("label");
  purposeFieldLabel.textContent = t("modalPurpose");
  const purposeSelect = document.createElement("select");
  PURPOSES.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = purposeLabel(p);
    opt.selected = p === item.purpose;
    purposeSelect.appendChild(opt);
  });
  purposeFieldLabel.appendChild(purposeSelect);
  body.appendChild(purposeFieldLabel);

  const repoInfo = document.createElement("div");
  repoInfo.className = "card-meta";
  repoInfo.id = "modal-repo-info";
  const fillRepoInfo = () => {
    while (repoInfo.firstChild) repoInfo.removeChild(repoInfo.firstChild);
    repoInfo.appendChild(renderStars(item.stars));
    if (item.url) repoInfo.appendChild(document.createTextNode(" · " + item.url));
  };
  fillRepoInfo();
  body.appendChild(repoInfo);

  const noteLabel = document.createElement("label");
  noteLabel.textContent = t("modalNote");
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
  save.textContent = t("save");
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
  del.textContent = t("delete");
  del.onclick = () => {
    if (!window.confirm(t("confirmDelete")(item.name))) return;
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
  refresh.textContent = t("refreshGithub");
  refresh.onclick = () => {
    showError(err, "");
    call("refresh_repo", { id: item.id }).then((updated) => {
      item.stars = updated.stars;
      item.url = updated.url;
      fillRepoInfo();
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
  if (e.key === "Escape" && addModalOpen) closeAddModal();

  // Digit shortcuts jump straight to a purpose tab (1 = Todos, 2..n = each
  // purpose in order, matching the <kbd> hint shown on the tab itself).
  const tag = (e.target && e.target.tagName) || "";
  const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
  if (!typing && !openModalId && !addModalOpen && !e.ctrlKey && !e.metaKey && !e.altKey) {
    const target = purposeTabTarget(e.key);
    if (target !== undefined) {
      filterPurpose = target;
      render();
    }
  }
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
  min-height: 56px;
  background: var(--surface);
  border-bottom: 3px solid var(--accent);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .75rem;
  padding: .5rem 1.25rem;
  position: sticky;
  top: 0;
  z-index: 10;
}
.topbar-title-group { display: flex; flex-direction: column; gap: .1rem; min-width: 0; }
.topbar h1 { font-size: 1.05rem; margin: 0; color: var(--accent); }
.topbar-subtitle { font-size: .74rem; color: var(--muted); }
.topbar-right { display: flex; align-items: center; gap: .75rem; flex-shrink: 0; }
.topbar-info { font-size: .78rem; color: var(--muted); }
@media (max-width: 720px) { .topbar-subtitle { display: none; } }

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

/* ---- Busca ---- */
.search-box { display: flex; align-items: center; gap: .5rem; margin-bottom: 1rem; }
.search-field { position: relative; flex: 1; min-width: 0; }
.search-actions { display: flex; align-items: center; gap: .4rem; flex-shrink: 0; }
.search-gh-btn { display: inline-flex; align-items: center; padding: .5rem .6rem; }

.gh-results { margin-bottom: 1rem; padding: .75rem; }
.gh-results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: .8rem;
  color: var(--muted);
  padding-bottom: .4rem;
  margin-bottom: .2rem;
  border-bottom: 1px solid var(--border);
}
.gh-results-close {
  background: none;
  border: none;
  color: var(--muted);
  font-size: .95rem;
  line-height: 1;
  cursor: pointer;
  padding: .1rem .3rem;
}
.gh-results-close:hover { color: var(--danger); }
.gh-results-status { font-size: .85rem; color: var(--muted); padding: .3rem 0; }
.gh-results-status.error { color: var(--danger); }
.gh-result { padding: .55rem 0; border-bottom: 1px solid var(--border); }
.gh-result:last-child { border-bottom: none; }
.gh-result-row {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: .75rem;
}
.gh-result-main { flex: 1; min-width: 0; }
.gh-result-name { font-size: .88rem; font-weight: 600; color: var(--accent); text-decoration: none; }
.gh-result-name:hover { text-decoration: underline; }
.gh-result-desc {
  font-size: .8rem;
  color: var(--muted);
  margin-top: .15rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gh-result-stars { flex-shrink: 0; }
.gh-result-add { flex-shrink: 0; }
.gh-result-error:not(:empty) { margin-top: .3rem; }
.search-icon {
  position: absolute;
  left: .7rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: .85rem;
  opacity: .6;
  pointer-events: none;
}
.search-input {
  width: 100%;
  box-sizing: border-box;
  padding: .55rem .75rem .55rem 2rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--strong);
  font-size: .9rem;
}
.search-input:focus { outline: none; border-color: var(--accent); }

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
.function-field {
  display: block;
  width: 100%;
  margin-top: .25rem;
  padding: .4rem .55rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--fg);
  font-size: .85rem;
  font-family: inherit;
  resize: vertical;
  min-height: 14rem; /* ~10 lines */
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
  -webkit-line-clamp: 10;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-meta { margin-top: .35rem; font-size: .72rem; color: var(--muted-2); word-break: break-word; }
.star { display: inline-flex; align-items: center; gap: .15rem; }
.star-icon { color: #f5b400; }
.star-count { color: var(--strong); font-weight: 600; }
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

/* ---- Pills de filtro por purpose, mesma cor do badge/section-head ----
   button.pill-purpose-* (elemento + classe) para vencer .btn na cascata:
   mesma especificidade de classe sozinha perderia por ordem de declaração. */
button.pill-purpose-general      { background: var(--c-general-bg);      color: var(--c-general-fg);      border-color: var(--c-general-fg); }
button.pill-purpose-devops       { background: var(--c-devops-bg);       color: var(--c-devops-fg);       border-color: var(--c-devops-fg); }
button.pill-purpose-spec-ops     { background: var(--c-spec-ops-bg);     color: var(--c-spec-ops-fg);     border-color: var(--c-spec-ops-fg); }
button.pill-purpose-quality      { background: var(--c-quality-bg);      color: var(--c-quality-fg);      border-color: var(--c-quality-fg); }
button.pill-purpose-security     { background: var(--c-security-bg);     color: var(--c-security-fg);     border-color: var(--c-security-fg); }
button.pill-purpose-integrations { background: var(--c-integrations-bg); color: var(--c-integrations-fg); border-color: var(--c-integrations-fg); }
button.pill-purpose-tooling      { background: var(--c-tooling-bg);      color: var(--c-tooling-fg);      border-color: var(--c-tooling-fg); }
button.pill-purpose-frontend     { background: var(--c-frontend-bg);     color: var(--c-frontend-fg);     border-color: var(--c-frontend-fg); }
button.pill-purpose-other        { background: var(--c-other-bg);        color: var(--c-other-fg);        border-color: var(--c-other-fg); }
button.pill-purpose-general.btn-primary, button.pill-purpose-devops.btn-primary, button.pill-purpose-spec-ops.btn-primary,
button.pill-purpose-quality.btn-primary, button.pill-purpose-security.btn-primary, button.pill-purpose-integrations.btn-primary,
button.pill-purpose-tooling.btn-primary, button.pill-purpose-frontend.btn-primary, button.pill-purpose-other.btn-primary,
button.pill-purpose-general.active, button.pill-purpose-devops.active, button.pill-purpose-spec-ops.active,
button.pill-purpose-quality.active, button.pill-purpose-security.active, button.pill-purpose-integrations.active,
button.pill-purpose-tooling.active, button.pill-purpose-frontend.active, button.pill-purpose-other.active {
  box-shadow: inset 0 0 0 2px currentColor;
}

/* ---- Aba de purpose: linha única, abas distribuídas lado a lado em vez
   da linha de pills (mesmas cores por purpose de antes) ---- */
.purpose-tabs {
  display: flex; margin-bottom: 1rem; border-radius: 8px;
  box-shadow: 0 0 0 1px var(--border);
  overflow-x: auto; overflow-y: hidden;
}
.purpose-tab {
  flex: 1 0 auto;
  display: flex; align-items: center; justify-content: center; gap: .4rem;
  padding: .5rem .7rem;
  border: none; border-right: 1px solid var(--border);
  background: var(--surface); color: var(--fg);
  font: inherit; font-size: .85rem; cursor: pointer; white-space: nowrap;
}
.purpose-tab:last-child { border-right: none; }
.purpose-tab.active { font-weight: 600; box-shadow: inset 0 -3px 0 0 currentColor; }
.tab-shortcut {
  font-size: .7rem; opacity: .6; border: 1px solid currentColor; border-radius: 4px;
  padding: 0 .3rem; line-height: 1.4;
}

/* ---- Pills de filtro por status, mesma cor do badge/borda do card ---- */
button.badge-candidata { background: var(--c-candidata-bg); color: var(--c-candidata-fg); border-color: var(--c-candidata-fg); }
button.badge-aprovada  { background: var(--c-aprovada-bg);  color: var(--c-aprovada-fg);  border-color: var(--c-aprovada-fg); }
button.badge-rejeitada { background: var(--c-rejeitada-bg); color: var(--c-rejeitada-fg); border-color: var(--c-rejeitada-fg); }
button.badge-candidata.btn-primary, button.badge-aprovada.btn-primary, button.badge-rejeitada.btn-primary {
  box-shadow: inset 0 0 0 2px currentColor;
}

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
