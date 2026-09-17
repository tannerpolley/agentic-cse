from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ScriptBehaviorTests(unittest.TestCase):
    def run_script(self, path: str, *args: str, env: dict[str, str] | None = None, cwd: Path = ROOT):
        return subprocess.run(
            ["bash", str(ROOT / path), *args] if path.endswith(".sh") else [sys.executable, str(ROOT / path), *args],
            cwd=cwd, env=env or os.environ.copy(), text=True, capture_output=True, check=False,
        )

    def git_fixture(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"], cwd=root, check=True)

    def test_sync_entrypoint_is_executable(self):
        self.assertTrue(os.access(ROOT / "scripts/sync-live.sh", os.X_OK))

    def test_inventory_stages_one_payload_and_excludes_repository_only_files(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "staged"
            generated = ROOT / "plugin/scripts/workflow/__pycache__/cse-test-generated"
            generated.mkdir(parents=True, exist_ok=True)
            (generated / "generated.pyc").write_bytes(b"generated")
            try:
                result = self.run_script("scripts/package_inventory.py", "stage", "cse", str(destination), "--commit", "0" * 40)
                self.assertEqual(0, result.returncode, result.stderr)
                identity = json.loads(result.stdout)
                self.assertEqual("cse", identity["pluginId"])
                self.assertEqual(22, len(identity["payloadSkills"]))
                self.assertIn("prose", identity["payloadSkills"])
                for excluded in ("tests", "evaluation", ".runs", "docs", "examples", "AGENTS.md", ".claude-plugin/marketplace.json"):
                    self.assertFalse((destination / excluded).exists(), excluded)
                self.assertFalse(any(
                    path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
                    for path in destination.rglob("*")
                ))
            finally:
                shutil.rmtree(generated, ignore_errors=True)

    def test_repo_hooks_survive_plugin_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "plugin"
            home = root / "home"
            repository = root / "repo"
            shutil.copytree(ROOT / "plugin", plugin)
            repository.mkdir()
            project = repository / "engine"
            context = project / "docs/scientific/CONTEXT.md"
            context.parent.mkdir(parents=True)
            context.write_text("# Scientific context\n")
            old_config = project / ".codex/hooks.json"
            old_config.parent.mkdir(parents=True)
            old_config.write_text(json.dumps({"description": "Project hook notes"}))

            claude_project = repository / "claude-engine"
            claude_context = claude_project / "docs/scientific/CONTEXT.md"
            claude_context.parent.mkdir(parents=True)
            claude_context.write_text("# Scientific context\n")
            claude_settings = claude_project / ".claude/settings.json"
            claude_settings.parent.mkdir(parents=True)
            claude_settings.write_text(json.dumps({
                "permissions": {"allow": ["Read"]},
                "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "other"}]}]},
            }))
            self.git_fixture(repository)

            installed = subprocess.run(
                [sys.executable, str(plugin / "scripts/workflow/install_cse_hooks.py"),
                 "--home", str(home), "--replace-runtime", "--repo", str(project)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(0, installed.returncode, installed.stderr)

            claude_command = [
                sys.executable, str(plugin / "scripts/workflow/install_cse_hooks.py"),
                "--home", str(home), "--agent", "claude", "--repo", str(claude_project),
            ]
            first_claude_settings = None
            for _ in range(2):
                installed_claude = subprocess.run(
                    claude_command, text=True, capture_output=True, check=False,
                )
                self.assertEqual(0, installed_claude.returncode, installed_claude.stderr)
                if first_claude_settings is None:
                    first_claude_settings = claude_settings.read_bytes()
                else:
                    self.assertEqual(first_claude_settings, claude_settings.read_bytes())
            claude_config = json.loads(claude_settings.read_text())
            self.assertEqual({"allow": ["Read"]}, claude_config["permissions"])
            self.assertEqual("other", claude_config["hooks"]["Stop"][0]["hooks"][0]["command"])
            self.assertEqual({"SessionStart", "SubagentStart", "UserPromptSubmit", "Stop"},
                             set(claude_config["hooks"]))
            for groups in claude_config["hooks"].values():
                for group in groups:
                    for handler in group["hooks"]:
                        if "cse-test-gate.py" in handler.get("command", ""):
                            self.assertNotIn("statusMessage", handler)

            unrelated = root / "unrelated"
            unrelated_context = unrelated / "docs/scientific/CONTEXT.md"
            unrelated_context.parent.mkdir(parents=True)
            unrelated_context.write_text("# Scientific context\n")
            unrelated_hooks = unrelated / ".codex/hooks.json"
            unrelated_hooks.parent.mkdir()
            unrelated_hooks.write_text('{"description":"User hook notes","hooks":{"Stop":[{"hooks":[{"command":"other"}]}]}}')
            self.git_fixture(unrelated)
            refused = subprocess.run(
                [sys.executable, str(plugin / "scripts/workflow/install_cse_hooks.py"),
                 "--home", str(home), "--repo", str(unrelated)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(0, refused.returncode, refused.stderr)
            self.assertEqual("User hook notes", json.loads(unrelated_hooks.read_text())["description"])
            self.assertEqual({"hooks": [{"command": "other"}]},
                             json.loads(unrelated_hooks.read_text())["hooks"]["Stop"][0])

            shutil.rmtree(plugin)
            config = json.loads((project / ".codex/hooks.json").read_text())
            self.assertEqual({"SessionStart", "SubagentStart", "UserPromptSubmit", "Stop"},
                             set(config["hooks"]))
            environment = {**os.environ, "HOME": str(home)}
            for event in config["hooks"]:
                command = config["hooks"][event][0]["hooks"][0]["command"]
                values = {"cwd": str(project), "session_id": "survives-plugin-removal"}
                if event == "SessionStart":
                    values["source"] = "startup"
                result = subprocess.run(
                    command, shell=True, input=json.dumps(values), env=environment,
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                if result.stdout:
                    json.loads(result.stdout)
            self.assertTrue((home / ".local/share/cse/hooks/cse_hook_common.py").is_file())
            self.assertTrue((home / ".local/share/cse/hooks/cse-scientific-stance.txt").is_file())
            self.assertNotIn("plugins/cache", json.dumps(config))

    def test_visualization_and_source_helpers_have_single_payload_locations(self):
        for relative in (
            "plugin/scripts/sources/sync_bibliography.py",
            "plugin/scripts/visualize/latex_visual_qa.py",
            "plugin/assets/visualize/project/quarto/render.sh",
            "plugin/assets/workflow/codex/hooks.json",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
