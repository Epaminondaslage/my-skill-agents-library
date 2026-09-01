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

**Stack**: Python 3.9+ stdlib only, bash, nginx, cron. No pip, no npm, no
build step at the code level. Two deploy modes, same source tree:

- **Bare-metal** (`install.sh`, systemd-sandboxed): edits host nginx +
  installs a systemd unit. `/opt/skill-agents-library` (root-owned, deploy
  via `install.sh | sudo bash`, never edit there),
  `/var/www/html/my-skill-agents-library` (generated), still the sole target
  paths on this mode.
- **Docker** (`Dockerfile` + `docker-compose.yml`, the deployed mode on this
  server): one container runs nginx + `src/serve.py` over an internal unix
  socket, isolation is the container boundary, no host nginx/systemd touched.
  Static site and socket live inside the container filesystem only.
  `docker compose up -d --build`, published on host port 8092. State
  (`items.json`, audit log, regen.request) bind-mounts from
  `~/.claude/.skill-library`; `~/.claude/.inventory` (auth hash) bind-mounts
  read-only. Cron is replaced by an hourly loop in `docker/entrypoint.sh`.
  `src/uninstall.sh` reverses the bare-metal mode only — for docker, `docker
  compose down`.

**Structure**: `src/` (generator, seed importer, backend, install/uninstall
scripts, systemd unit template), `install.sh` (bare-metal bootstrap),
`docker/` (nginx.conf, entrypoint.sh for the container mode), `tests/`.

State (both modes): `~/.claude/.skill-library/` (items.json, audit log,
status, regen request) is the sole source of truth, mutated only through
`src/api.py`.

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
