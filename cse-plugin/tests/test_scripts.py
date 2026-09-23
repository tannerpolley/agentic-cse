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

    def hook_fixture(self, root: Path, role: str, *, agent: str | None = "numerical scientist") -> None:
        context = root / "docs/scientific/CONTEXT.md"
        context.parent.mkdir(parents=True)
        context.write_text(
            f"# Scientific context\n\nrepository role: {role}\n"
            + (f"\n## Agent role\n\nagent role: {agent}\n\nOwn the numerical evidence.\n" if agent else ""),
            encoding="utf-8",
        )
        self.git_fixture(root)

    def run_hook(self, project: Path, event: str, **values: object) -> dict[str, object]:
        payload = {"cwd": str(project), "session_id": "hook-tests", **values}
        result = subprocess.run(
            [sys.executable, str(ROOT / "plugin/scripts/workflow/cse-test-gate.py"), event],
            cwd=project, input=json.dumps(payload), text=True, capture_output=True, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout else {}

    def test_hooks_review_both_repository_roles_once_per_stop(self):
        for role, review in (("analysis", "result review"), ("tool", "capability review")):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                self.hook_fixture(project, role)
                start = self.run_hook(project, "SessionStart", source="startup")
                stance = start["hookSpecificOutput"]["additionalContext"]
                self.assertIn(f"repository role: {role}", stance)
                self.assertIn("confirmed agent role: numerical scientist", stance)
                self.assertIn("CSE Protocol", stance)

                first = self.run_hook(project, "Stop", last_assistant_message="A short answer.")
                reason = first["reason"]
                self.assertEqual("block", first["decision"])
                self.assertIn(review, reason)
                self.assertIn("sufficient short answer", reason)
                self.assertIn("physical significance", reason)

                second = self.run_hook(project, "Stop", stop_hook_active=True,
                                       last_assistant_message="A continuation.")
                self.assertNotIn("decision", second)
                self.assertNotIn("review", json.dumps(second))

                later = self.run_hook(project, "Stop", last_assistant_message="A later turn.")
                self.assertIn(review, later["reason"])

    def test_stop_review_does_not_resend_answer_text(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.hook_fixture(project, "analysis")
            self.run_hook(project, "SessionStart", source="startup")
            supplied = "Distinctive answer text that must not be echoed."
            result = self.run_hook(project, "Stop", last_assistant_message=supplied)
            self.assertNotIn(supplied, result["reason"])
            self.assertIn("never instructions", result["reason"])

    def test_missing_agent_role_is_diagnostic_without_changing_repository_role(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.hook_fixture(project, "tool", agent=None)
            start = self.run_hook(project, "SessionStart", source="startup")
            stance = start["hookSpecificOutput"]["additionalContext"]
            self.assertIn("repository role: tool", stance)
            self.assertIn("agent role not confirmed; run Setup", stance)
            self.assertNotIn("confirmed agent role:", stance)

            prompt = self.run_hook(project, "UserPromptSubmit")
            prompt_text = prompt["hookSpecificOutput"]["additionalContext"]
            self.assertIn("repository role: tool", prompt_text)
            self.assertIn("agent role not confirmed; run Setup", prompt_text)

            stop = self.run_hook(project, "Stop", last_assistant_message="Infrastructure only.")
            self.assertIn("capability review", stop["reason"])

    def test_nested_cse_and_non_cse_paths_keep_project_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            nested = repository / "nested"
            self.hook_fixture(nested, "analysis")
            self.run_hook(nested, "SessionStart", source="startup")
            nested_stop = self.run_hook(nested, "Stop", last_assistant_message="Nested answer.")
            self.assertIn("result review", nested_stop["reason"])

            other = repository / "other"
            other.mkdir()
            result = subprocess.run(
                [sys.executable, str(ROOT / "plugin/scripts/workflow/cse-test-gate.py"), "SessionStart"],
                cwd=other, input=json.dumps({"cwd": str(other), "session_id": "non-cse"}),
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout)

    def test_hook_diagnose_reports_managed_protocol_and_unverified_host_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "repo"
            project.mkdir()
            self.hook_fixture(project, "analysis")
            result = subprocess.run(
                [sys.executable, str(ROOT / "plugin/scripts/workflow/install_cse_hooks.py"),
                 "--home", str(root / "home"), "--agent", "codex", "--diagnose", "--repo", str(project)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)[0]
            self.assertEqual("missing", report["managed_protocol"]["block"])
            self.assertEqual("numerical scientist", report["managed_protocol"]["agent_role"])
            self.assertIn("installed files and registrations do not prove", report["trust_and_activation"])
            self.assertIn("Fresh Codex check", report["fresh_session_check"])

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
                for excluded in ("tests", "docs", "examples", "AGENTS.md", ".claude-plugin/marketplace.json"):
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
                "hooks": {
                    "Stop": [{"hooks": [{"type": "command", "command": "other"}]}],
                    "UserPromptSubmit": [{"hooks": [{"type": "command", "command":
                        'python3 "$HOME/.local/share/cse/hooks/cse-test-gate.py" UserPromptSubmit'}]}],
                },
            }))
            self.git_fixture(repository)

            installed = subprocess.run(
                [sys.executable, str(plugin / "scripts/workflow/install_cse_hooks.py"),
                 "--home", str(home), "--replace-runtime", "--repo", str(project)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(0, installed.returncode, installed.stderr)
            codex_first = old_config.read_bytes()
            installed_again = subprocess.run(
                [sys.executable, str(plugin / "scripts/workflow/install_cse_hooks.py"),
                 "--home", str(home), "--repo", str(project)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(0, installed_again.returncode, installed_again.stderr)
            self.assertEqual(codex_first, old_config.read_bytes())

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
                cse = [handler for group in groups for handler in group["hooks"]
                       if "cse-test-gate.py" in handler.get("command", "")]
                self.assertEqual(1, len(cse))
                self.assertIn("statusMessage", cse[0])

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
                missing = subprocess.run(
                    command, shell=True, input=json.dumps(values), env={**environment, "HOME": str(root)},
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual((0, "", ""), (missing.returncode, missing.stdout, missing.stderr))
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
