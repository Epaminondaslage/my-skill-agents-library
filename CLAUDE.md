# My Skill-Agents Library

## Codebase Overview

Self-hosted, offline-first CRUD catalog for skill/plugin *suggestions* the
user comes across — separate from my-Harness-Library, which inventories
what's already installed. Each item carries a status
(`candidata`/`aprovada`/`rejeitada`) and a personal note, so decisions on
whether to install can be made later. `src/seed.py` imports the initial set
from my-Harness-Library's `Catalogo-de-Agent-Skills.md` (one-time only);
after that, `~/.claude/.skill-library/items.json` is the sole source of
truth, mutated only through `src/api.py`. `src/generator.py` renders it to a
static 3-file site; `src/regenerate.sh` runs it from cron or on-demand.

**Stack**: Python 3.9+ stdlib only, bash, systemd, nginx, cron. No pip, no
npm, no build step.

**Structure**: `src/` (generator, seed importer, backend, install/uninstall
scripts, systemd unit template), `install.sh` (bootstrap), `tests/`.

Runtime on the server: `/opt/skill-agents-library` (root-owned, deploy via
`install.sh | sudo bash`, never edit there), `/var/www/html/my-skill-agents-library`
(generated), `~/.claude/.skill-library/` (state: items.json, audit log,
status, regen request).

Auth is shared with my-Harness-Library: this project reads (never writes)
`~/.claude/.inventory/auth.hash`.

## Working rules

- Keep it stdlib-only and offline-first.
- State lives only under `~/.claude/.skill-library/`; the backend sandbox
  sees nothing else writable.
- The backend must never spawn processes — regeneration goes through
  `regen.request`, consumed by cron.
- Verify before claiming done: `bash -n` on scripts, `python3 -m py_compile
  src/*.py`, `python3 -m unittest discover tests`, `node --check` the
  emitted `app.js`.
