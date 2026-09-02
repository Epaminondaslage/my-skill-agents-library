#!/usr/bin/env python3
# =============================================================================
# detect_installed.py — one-time cross-reference: marks which catalog items
# are actually installed for Claude Code and/or Codex on this machine, so the
# generated page can show a "Claude" / "Codex" badge on them. Never invoked
# by serve.py/api.py or cron — run by hand, like enrich.py, whenever you want
# the badges refreshed.
#
# What counts as "installed" is real filesystem/config state, not CLAUDE.md
# or AGENTS.md prose — neither file is a manifest (CLAUDE.md is freeform
# instructions; a global AGENTS.md is typically empty). The actual signal:
#   Claude — ~/.claude/skills/*, ~/.claude/agents/*.md, ~/.claude/commands/**/*.md,
#            plugin names from ~/.claude/plugins/installed_plugins.json,
#            MCP server names from ~/.claude.json's mcpServers blocks.
#   Codex  — ~/.codex/skills/* (excluding dotdirs like .system),
#            MCP server names from [mcp_servers.<name>] tables in
#            ~/.codex/config.toml.
# Deliberately NOT scanned: plugin/marketplace *catalogs* (e.g.
# ~/.claude/plugins/marketplaces/*, ~/.codex/.tmp/plugins/*) — those list
# what COULD be installed from that marketplace, not what actually is.
# =============================================================================

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def _slug(name: str) -> str:
    """Normalizes a name for matching: lowercase, non-alnum runs collapsed
    to a single hyphen, trimmed. Makes "Claude Skills" == "claude-skills"
    == "claude_skills" == "ClaudeSkills"-ish (word boundaries still count)."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def scan_claude_installed(claude_home: Path) -> set[str]:
    names: set[str] = set()

    skills_dir = claude_home / "skills"
    if skills_dir.is_dir():
        for md in skills_dir.glob("*/SKILL.md"):
            names.add(_slug(md.parent.name))

    agents_dir = claude_home / "agents"
    if agents_dir.is_dir():
        for md in agents_dir.rglob("*.md"):
            names.add(_slug(md.stem))

    commands_dir = claude_home / "commands"
    if commands_dir.is_dir():
        for md in commands_dir.rglob("*.md"):
            names.add(_slug(md.stem))

    installed_plugins = claude_home / "plugins" / "installed_plugins.json"
    if installed_plugins.is_file():
        try:
            data = json.loads(installed_plugins.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for key in data.get("plugins", {}):
            plugin_name = key.split("@", 1)[0]
            names.add(_slug(plugin_name))

    claude_json = claude_home.parent / ".claude.json"
    if claude_json.is_file():
        try:
            data = json.loads(claude_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for server_name in _all_mcp_server_names(data):
            names.add(_slug(server_name))

    return names


def _all_mcp_server_names(data: dict) -> set[str]:
    """~/.claude.json has a top-level "mcpServers" object and/or one per
    project under "projects"."""
    names: set[str] = set()
    names.update(data.get("mcpServers", {}).keys())
    for project in data.get("projects", {}).values():
        if isinstance(project, dict):
            names.update(project.get("mcpServers", {}).keys())
    return names


_TOML_TABLE_RE = re.compile(r"^\[mcp_servers\.([^\].]+)\]\s*$")


def scan_codex_installed(codex_home: Path) -> set[str]:
    names: set[str] = set()

    skills_dir = codex_home / "skills"
    if skills_dir.is_dir():
        for entry in skills_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                names.add(_slug(entry.name))

    config_toml = codex_home / "config.toml"
    if config_toml.is_file():
        # Deliberately not a full TOML parse (stdlib-only, no tomllib
        # dependency assumed) — just enough to pull out mcp_servers table
        # names, which is all that's needed here.
        for line in config_toml.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _TOML_TABLE_RE.match(line.strip())
            if m:
                names.add(_slug(m.group(1)))

    return names


def mark_installed(items: list[dict], claude_names: set[str], codex_names: set[str]) -> list[dict]:
    """Returns a new list with installed_claude/installed_codex booleans set
    on every item, matching by a normalized slug of the item's name (and,
    if present, the repo's own name — the part after the last "/")."""
    result = []
    for original in items:
        item = dict(original)
        candidates = {_slug(item.get("name", ""))}
        repo = item.get("repo", "")
        if repo:
            candidates.add(_slug(repo.rsplit("/", 1)[-1]))
        item["installed_claude"] = bool(candidates & claude_names)
        item["installed_codex"] = bool(candidates & codex_names)
        result.append(item)
    return result


def main(items_path: Path, claude_home: Path, codex_home: Path) -> None:
    items = json.loads(items_path.read_text(encoding="utf-8"))
    claude_names = scan_claude_installed(claude_home)
    codex_names = scan_codex_installed(codex_home)
    marked = mark_installed(items, claude_names, codex_names)

    tmp_path = items_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(marked, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, items_path)

    n_claude = sum(1 for i in marked if i["installed_claude"])
    n_codex = sum(1 for i in marked if i["installed_codex"])
    print(f"detected {n_claude} installed (Claude), {n_codex} installed (Codex) of {len(marked)} items -> {items_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: detect_installed.py <items.json>", file=sys.stderr)
        raise SystemExit(2)
    main(Path(sys.argv[1]), Path.home() / ".claude", Path.home() / ".codex")
