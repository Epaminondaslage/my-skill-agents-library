import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import detect_installed as di  # noqa: E402


def item(**overrides):
    base = {
        "id": "abc123", "name": "foo", "repo": "o/f", "url": "", "stars": 0,
        "function": "does stuff", "dev_note": "1/10",
        "kind": "skill", "purpose": "other", "status": "candidata",
        "personal_note": "", "decided_at": None,
        "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


class TestSlug(unittest.TestCase):
    def test_normalizes_case_and_separators(self):
        self.assertEqual(di._slug("Claude Skills"), "claude-skills")
        self.assertEqual(di._slug("claude_skills"), "claude-skills")
        self.assertEqual(di._slug("claude-skills"), "claude-skills")
        self.assertEqual(di._slug("  Claude   Skills!! "), "claude-skills")


class TestScanClaudeInstalled(unittest.TestCase):
    def test_scans_skills_agents_commands_plugins_and_mcp(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            claude_home = home / ".claude"

            (claude_home / "skills" / "avoid-ai-writing").mkdir(parents=True)
            (claude_home / "skills" / "avoid-ai-writing" / "SKILL.md").write_text("x")

            (claude_home / "agents").mkdir(parents=True)
            (claude_home / "agents" / "claude-code-guide.md").write_text("x")

            (claude_home / "commands").mkdir(parents=True)
            (claude_home / "commands" / "deploy-prod.md").write_text("x")

            (claude_home / "plugins").mkdir(parents=True)
            (claude_home / "plugins" / "installed_plugins.json").write_text(json.dumps({
                "plugins": {"superpowers@claude-plugins-official": [{}]}
            }))

            (home / ".claude.json").write_text(json.dumps({
                "mcpServers": {"playwright": {}},
                "projects": {"/opt/foo": {"mcpServers": {"coolify": {}}}},
            }))

            names = di.scan_claude_installed(claude_home)
            self.assertEqual(names, {
                "avoid-ai-writing", "claude-code-guide", "deploy-prod",
                "superpowers", "playwright", "coolify",
            })

    def test_empty_home_returns_empty_set(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(di.scan_claude_installed(Path(d) / ".claude"), set())


class TestScanCodexInstalled(unittest.TestCase):
    def test_scans_skills_dir_and_mcp_servers_toml(self):
        with tempfile.TemporaryDirectory() as d:
            codex_home = Path(d) / ".codex"
            (codex_home / "skills" / "tarefa-finalizada").mkdir(parents=True)
            (codex_home / "skills" / ".system").mkdir(parents=True)  # excluded (dotdir)

            (codex_home).mkdir(exist_ok=True)
            (codex_home / "config.toml").write_text(
                "[mcp_servers.playwright]\n"
                "command = \"npx\"\n"
                "args = [\"@playwright/mcp@latest\"]\n"
                "\n"
                "[mcp_servers.coolify]\n"
                "command = \"npx\"\n"
            )

            names = di.scan_codex_installed(codex_home)
            self.assertEqual(names, {"tarefa-finalizada", "playwright", "coolify"})

    def test_missing_dirs_return_empty_set(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(di.scan_codex_installed(Path(d) / ".codex"), set())


class TestMarkInstalled(unittest.TestCase):
    def test_matches_by_name_or_repo_basename(self):
        items = [
            item(name="avoid-ai-writing", repo="o/avoid-ai-writing"),
            item(name="Some Random Skill", repo="o/completely-different"),
            item(name="Playwright MCP", repo="microsoft/playwright"),
        ]
        result = di.mark_installed(items, claude_names={"avoid-ai-writing"}, codex_names={"playwright"})
        self.assertTrue(result[0]["installed_claude"])
        self.assertFalse(result[0]["installed_codex"])
        self.assertFalse(result[1]["installed_claude"])
        self.assertFalse(result[1]["installed_codex"])
        self.assertFalse(result[2]["installed_claude"])
        self.assertTrue(result[2]["installed_codex"])  # matched via repo basename "playwright"

    def test_does_not_mutate_original_items(self):
        items = [item(name="foo")]
        di.mark_installed(items, claude_names={"foo"}, codex_names=set())
        self.assertNotIn("installed_claude", items[0])


class TestMain(unittest.TestCase):
    def test_writes_installed_flags_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            items_path = base / "items.json"
            items_path.write_text(json.dumps([item(name="avoid-ai-writing")]))

            claude_home = base / ".claude"
            (claude_home / "skills" / "avoid-ai-writing").mkdir(parents=True)
            (claude_home / "skills" / "avoid-ai-writing" / "SKILL.md").write_text("x")
            codex_home = base / ".codex"

            di.main(items_path, claude_home, codex_home)

            result = json.loads(items_path.read_text())
            self.assertTrue(result[0]["installed_claude"])
            self.assertFalse(result[0]["installed_codex"])
            self.assertFalse((base / "items.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
