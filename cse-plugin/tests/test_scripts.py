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
    def run_script(self, script: str, *arguments: str):
        path = ROOT / script if "/" in script else ROOT / "scripts" / script
        return subprocess.run(
            [sys.executable, str(path), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )

    def initialize_git_repository(self, root: Path, branch: str = "main"):
        subprocess.run(["git", "init", "-q", "-b", branch], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
        )

    def commit_all(self, root: Path, message: str):
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", message], cwd=root, check=True)

    def test_change_accounting_covers_branch_and_worktree_states(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_git_repository(root)
            (root / "src").mkdir()
            (root / "src/model.py").write_text("value = 1\n")
            (root / "tests").mkdir()
            (root / "tests/test_model.py").write_text("assert True\n")
            (root / "docs").mkdir()
            (root / "docs/method.md").write_text("baseline\n")
            (root / ".gitignore").write_text("ignored.bin\n")
            self.commit_all(root, "baseline")
            subprocess.run(["git", "switch", "-qc", "feature"], cwd=root, check=True)

            (root / "src/model.py").write_text("value = 2\nextra = 3\n")
            self.commit_all(root, "committed implementation")
            (root / "tests/test_model.py").write_text("assert 2 == 2\n")
            subprocess.run(["git", "add", "tests/test_model.py"], cwd=root, check=True)
            (root / "docs/method.md").write_text("revised\n")
            (root / "generated").mkdir()
            (root / "generated/result.py").write_text("generated = True\n")
            (root / "figure.bin").write_bytes(b"\x00\x01\x02")
            (root / "ignored.bin").write_bytes(b"\x00ignored")

            result = self.run_script(
                "change_accounting.py", "--repo", str(root), "--base", "main", "--json"
            )
            report = json.loads(result.stdout)
            files = {record["path"]: record for record in report["files"]}

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(files["src/model.py"]["category"], "executable")
        self.assertEqual(files["tests/test_model.py"]["category"], "tests")
        self.assertEqual(files["docs/method.md"]["category"], "documents")
        self.assertEqual(files["generated/result.py"]["category"], "generated")
        self.assertTrue(files["generated/result.py"]["untracked"])
        self.assertTrue(files["figure.bin"]["binary"])
        self.assertIsNone(files["figure.bin"]["additions"])
        self.assertNotIn("ignored.bin", files)
        self.assertEqual(report["categories"]["executable"]["additions"], 2)
        self.assertEqual(report["categories"]["executable"]["removals"], 1)
        self.assertNotIn("executable_removal_to_addition_ratio", report)

    def test_change_accounting_detects_default_base_and_renders_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_git_repository(root)
            (root / "README.md").write_text("baseline\n")
            self.commit_all(root, "baseline")
            subprocess.run(["git", "switch", "-qc", "feature"], cwd=root, check=True)
            (root / "README.md").write_text("revision\n")
            result = self.run_script("change_accounting.py", "--repo", str(root))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("requested base: main", result.stdout)
        self.assertIn("executable: 0 files, +0 -0, 0 binary", result.stdout)
        self.assertNotIn("removal/addition ratio", result.stdout)
        self.assertIn("documents: +1 -1 README.md", result.stdout)

    def test_change_accounting_rejects_non_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_script("change_accounting.py", "--repo", directory)
        self.assertEqual(result.returncode, 2)
        self.assertIn("not a Git repository", result.stderr)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_git_repository(root, "trunk")
            (root / "input.txt").write_text("value\n")
            self.commit_all(root, "baseline")
            result = self.run_script("change_accounting.py", "--repo", str(root))
        self.assertEqual(result.returncode, 2)
        self.assertIn("provide --base REF", result.stderr)

    def test_cse_hook_refreshes_stance_and_reports_test_advisory_without_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repo"
            repository.mkdir()
            self.initialize_git_repository(repository)
            project = repository / "engine"
            context = project / "docs/scientific/CONTEXT.md"
            context.parent.mkdir(parents=True)
            context.write_text("# Scientific context\n")
            tests = project / "tests"
            tests.mkdir()
            existing = tests / "test_model.py"
            original = "assert True\nassert 2 == 2\n"
            existing.write_text(original)
            removed = tests / "test_removed.py"
            removed.write_text("assert True\n")
            target = tests / "target.py"
            target.write_text("assert True\n")
            (tests / "test_link.py").symlink_to(target.name)
            self.commit_all(repository, "baseline")

            hook = ROOT / "scripts/cse-test-gate.py"
            stance_template = (ROOT / "assets/codex/scientific-stance.txt").read_text().strip()
            serial = 0

            def invoke(event: str, **values):
                result = subprocess.run(
                    [sys.executable, str(hook), event],
                    input=json.dumps({"cwd": str(project), **values}),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout) if result.stdout else {}

            def start():
                nonlocal serial
                serial += 1
                return invoke("SessionStart", source="startup", session_id=f"session-{serial}")

            def expected_stance(deliverable=None):
                start_index = stance_template.index("[[")
                end_index = stance_template.index("]]", start_index)
                optional = stance_template[start_index + 2:end_index]
                clause = optional.replace("{deliverable}", deliverable) if deliverable else ""
                return stance_template[:start_index] + clause + stance_template[end_index + 2:]

            for context_text, deliverable, opening in (
                ("# Scientific context\ndefault deliverable: result\n", "result",
                 "This is a CSE scientific repository, default deliverable: result."),
                ("# Scientific context\ndefault deliverable: capability\n", "capability",
                 "This is a CSE scientific repository, default deliverable: capability."),
                ("# Scientific context\n", None, "This is a CSE scientific repository."),
                ("# Scientific context\ndefault deliverable: report\n", None,
                 "This is a CSE scientific repository."),
            ):
                context.write_text(context_text)
                rendered = start()["hookSpecificOutput"]["additionalContext"]
                self.assertEqual(expected_stance(deliverable), rendered)
                self.assertTrue(rendered.startswith(opening))
                self.assertLessEqual(len(rendered.split()), 180)
            context.write_text("# Scientific context\n")

            output = invoke("SubagentStart", session_id=f"session-{serial}")
            self.assertEqual(expected_stance(), output["hookSpecificOutput"]["additionalContext"])
            reminder = invoke("UserPromptSubmit", session_id=f"session-{serial}")["hookSpecificOutput"]["additionalContext"]
            self.assertLess(len(reminder.split()), 35)
            self.assertIn("scientific question", reminder)

            start()
            self.assertEqual({}, invoke("Stop", session_id=f"session-{serial}"))
            self.assertEqual({}, invoke("Stop", session_id=f"session-{serial}", stop_hook_active=False))
            self.assertEqual({}, invoke("Stop", session_id=f"session-{serial}", stop_hook_active=True))
            unavailable = invoke("Stop", session_id="missing-baseline", stop_hook_active=True)
            self.assertNotIn("decision", unavailable)
            self.assertIn("not a pass", unavailable["systemMessage"])
            for state in (repository / ".git/cse-test-advisory").glob("*.json"):
                state.write_text("[]")
            invalid = invoke("Stop", session_id=f"session-{serial}", stop_hook_active=True)
            self.assertNotIn("decision", invalid)
            self.assertIn("not a pass", invalid["systemMessage"])
            start()
            resumed = invoke("SessionStart", source="compact", session_id=f"session-{serial}")
            self.assertEqual(expected_stance(), resumed["hookSpecificOutput"]["additionalContext"])

            probes = (
                (lambda: existing.write_text("assert True\n"), "expanded test: engine/tests/test_model.py"),
                (removed.unlink, "deleted test: engine/tests/test_removed.py"),
                (lambda: existing.write_text(original + "# comment\n"), "expanded test: engine/tests/test_model.py"),
                (lambda: (tests / "test_new.py").write_text("assert True\n"), "new test: engine/tests/test_new.py"),
            )
            for mutate, expected in probes:
                existing.write_text(original)
                removed.write_text("assert True\n")
                (tests / "test_new.py").unlink(missing_ok=True)
                start()
                mutate()
                advisory = invoke("Stop", session_id=f"session-{serial}")
                self.assertNotIn("decision", advisory)
                self.assertIn(expected, advisory["systemMessage"])
                repeated = invoke("Stop", session_id=f"session-{serial}", stop_hook_active=True)
                self.assertNotIn("decision", repeated)
                self.assertIn(expected, repeated["systemMessage"])

    def test_repo_hooks_survive_plugin_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "plugin"
            home = root / "home"
            repository = root / "repo"
            shutil.copytree(ROOT / "scripts", plugin / "scripts")
            shutil.copytree(ROOT / "assets", plugin / "assets")
            shutil.copy2(ROOT / "BANNED.md", plugin / "BANNED.md")
            repository.mkdir()
            self.initialize_git_repository(repository)
            project = repository / "engine"
            context = project / "docs/scientific/CONTEXT.md"
            context.parent.mkdir(parents=True)
            context.write_text("# Scientific context\n")
            old_events = (
                "SessionStart", "SubagentStart", "UserPromptSubmit",
                "PostToolUse", "SubagentStop", "Stop",
            )
            old_config = project / ".codex/hooks.json"
            old_config.parent.mkdir(parents=True)
            old_config.write_text(json.dumps({"hooks": {
                event: [{"hooks": [{
                    "type": "command",
                    "command": f'/usr/bin/python3 "$HOME/.codex/hooks/cse-test-gate.py" {event}',
                }]}]
                for event in old_events
            }}))
            self.commit_all(repository, "baseline")

            installed = subprocess.run(
                [
                    sys.executable,
                    str(plugin / "scripts/install_cse_hooks.py"),
                    "--home",
                    str(home),
                    "--replace-runtime",
                    "--repo",
                    str(project),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)

            unrelated = root / "unrelated"
            unrelated.mkdir()
            self.initialize_git_repository(unrelated)
            unrelated_context = unrelated / "docs/scientific/CONTEXT.md"
            unrelated_context.parent.mkdir(parents=True)
            unrelated_context.write_text("# Scientific context\n")
            unrelated_hooks = unrelated / ".codex/hooks.json"
            unrelated_hooks.parent.mkdir()
            unrelated_hooks.write_text('{"description":"User hook notes","hooks":{"Stop":[{"hooks":[{"command":"other"}]}]}}')
            refused = subprocess.run(
                [sys.executable, str(plugin / "scripts/install_cse_hooks.py"),
                 "--home", str(home), "--repo", str(unrelated)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(refused.returncode, 0, refused.stderr)
            self.assertEqual(json.loads(unrelated_hooks.read_text())["description"], "User hook notes")
            self.assertEqual(json.loads(unrelated_hooks.read_text())["hooks"]["Stop"][0],
                             {"hooks": [{"command": "other"}]})
            shutil.rmtree(plugin)

            config = json.loads((project / ".codex/hooks.json").read_text())
            self.assertEqual(set(config["hooks"]), {"SessionStart", "SubagentStart", "UserPromptSubmit", "Stop"})
            environment = {**os.environ, "HOME": str(home)}
            base_event = {"cwd": str(project), "session_id": "survives-upgrade"}
            for event in ("SessionStart", "SubagentStart", "UserPromptSubmit", "Stop"):
                command = config["hooks"][event][0]["hooks"][0]["command"]
                self.assertTrue(command.startswith('python3 "$HOME/'))
                values = {**base_event}
                if event == "SessionStart":
                    values["source"] = "startup"
                result = subprocess.run(
                    command,
                    shell=True,
                    input=json.dumps(values),
                    env=environment,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                if result.stdout:
                    json.loads(result.stdout)

            self.assertTrue((home / ".local/share/cse/hooks/cse_hook_common.py").is_file())
            self.assertTrue((home / ".local/share/cse/hooks/cse-scientific-stance.txt").is_file())

            self.assertNotIn("plugins/cache", json.dumps(config))
            self.assertNotIn("PLUGIN_ROOT", json.dumps(config))
            self.assertNotIn("CLAUDE_PLUGIN_ROOT", json.dumps(config))

    def test_claude_hook_installation_preserves_settings_and_diagnoses_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            repo = root / "repo"
            repo.mkdir()
            self.initialize_git_repository(repo)
            context = repo / "docs/scientific/CONTEXT.md"
            context.parent.mkdir(parents=True)
            context.write_text("# Scientific context\n")
            config = repo / ".claude/settings.json"
            config.parent.mkdir()
            config.write_text(json.dumps({"permissions": {"deny": ["Bash(rm *)"]},
                "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo keep"}]}]}}))
            args = ("--agent", "claude", "--home", str(home), "--repo", str(repo))
            before = config.read_bytes()
            report = self.run_script("install_cse_hooks.py", *args, "--diagnose")
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertFalse(json.loads(report.stdout)[0]["configuration_current"])
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse(home.exists())
            installed = self.run_script("install_cse_hooks.py", *args)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            data = json.loads(config.read_text())
            self.assertEqual(data["permissions"], {"deny": ["Bash(rm *)"]})
            self.assertEqual(data["hooks"]["Stop"][0]["hooks"][0]["command"], "echo keep")
            self.assertNotIn("statusMessage", data["hooks"]["Stop"][1]["hooks"][0])
            self.assertFalse((repo / ".codex").exists())
            again = self.run_script("install_cse_hooks.py", *args)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(json.loads(config.read_text()), data)
            report = json.loads(self.run_script("install_cse_hooks.py", *args, "--diagnose").stdout)[0]
            self.assertTrue(report["configuration_current"])
            self.assertTrue(all(item["matches_source"] for item in report["runtime"]))
            self.assertIn("unverified", report["trust_and_activation"])
            runtime = home / ".local/share/cse/hooks"
            installed_file = runtime / "cse-test-gate.py"
            installed_file.unlink()
            installed_file.symlink_to(ROOT / "scripts/cse-test-gate.py")
            report = json.loads(self.run_script("install_cse_hooks.py", *args, "--diagnose").stdout)[0]
            self.assertFalse(report["runtime"][0]["matches_source"])
            self.assertIsNone(report["runtime"][0]["sha256"])
            self.assertIn("symlink", report["runtime"][0]["error"])
            installed_file.unlink()
            shutil.copyfile(ROOT / "scripts/cse-test-gate.py", installed_file)
            runtime.rename(runtime.with_name("real-hooks"))
            runtime.symlink_to(runtime.with_name("real-hooks"), target_is_directory=True)
            report = json.loads(self.run_script("install_cse_hooks.py", *args, "--diagnose").stdout)[0]
            self.assertTrue(all("symlink" in item["error"] for item in report["runtime"]))
            runtime.unlink()
            runtime.with_name("real-hooks").rename(runtime)
            config.unlink()
            config.parent.rmdir()
            config.parent.symlink_to(home, target_is_directory=True)
            refused = self.run_script("install_cse_hooks.py", *args)
            self.assertNotEqual(refused.returncode, 0)
            self.assertFalse((home / "settings.json").exists())

    def test_hook_diagnosis_separates_legacy_missing_targets_and_saved_disables(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, repo = root / "home", root / "repo"
            repo.mkdir()
            self.initialize_git_repository(repo)
            context = repo / "docs/scientific/CONTEXT.md"
            context.parent.mkdir(parents=True)
            context.write_text("# Scientific context\n")
            legacy = home / ".codex/hooks/cse-test-gate.py"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("legacy runtime; must not execute\n")
            settings = home / ".codex/config.toml"
            settings.write_text('[hooks.state."cse@personal:hooks/hooks.json:stop:0:0"]\nenabled = false\ntrusted_hash = "private"\n'
                                '[hooks.state."unrelated:stop"]\nenabled = true\n')
            configs = [home / ".codex/hooks.json", repo / ".codex/hooks.json"]
            for config, runtime in zip(configs, (".local/share/cse/hooks", ".codex/hooks")):
                config.parent.mkdir(exist_ok=True)
                config.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command",
                    "command": f'python3 "$HOME/{runtime}/cse-test-gate.py" Stop'}]}]}}))
            before = {path: path.read_bytes() for path in [settings, legacy, *configs]}
            result = self.run_script("install_cse_hooks.py", "--diagnose", "--home", str(home), "--repo", str(repo))
            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)[0]
            sources = {item["path"]: item for item in report["configuration_sources"]}
            self.assertFalse(sources[str(configs[0])]["registrations"][0]["target_exists"])
            registered = sources[str(configs[1])]["registrations"][0]
            self.assertTrue(registered["target_exists"])
            self.assertTrue(registered["legacy"])
            self.assertEqual({"cse@personal:hooks/hooks.json:stop:0:0": {"enabled": False}},
                             sources[str(settings)]["saved_cse_state"])
            self.assertNotIn("private", result.stdout)
            self.assertIn("unverified", report["trust_and_activation"])
            self.assertFalse((home / ".local").exists())
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_hook_diagnosis_retains_other_sources_and_repositories_after_malformed_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            repos = [root / "bad", root / "good"]
            for repo in repos:
                repo.mkdir()
                self.initialize_git_repository(repo)
                context = repo / "docs/scientific/CONTEXT.md"
                context.parent.mkdir(parents=True)
                context.write_text("# Scientific context\n")
            for agent, relative in (("codex", ".codex/hooks.json"), ("claude", ".claude/settings.json")):
                configs = [base / relative for base in [home, *repos]]
                for config in configs:
                    config.parent.mkdir(parents=True, exist_ok=True)
                    config.write_text('{"hooks": {}}')
                configs[0].write_text('{"hooks": {"Stop": {}}}')
                for malformed in ('{"hooks":{"Stop":{}}}', '{"hooks":{"Stop":[{}]}}',
                                  '{"hooks":{"Stop":[{"hooks":[{"type":"command","command":null}]}]}}', '{'):
                    with self.subTest(agent=agent, malformed=malformed):
                        configs[1].write_text(malformed)
                        before = {path: path.read_bytes() for path in configs}
                        result = self.run_script("install_cse_hooks.py", "--diagnose", "--agent", agent,
                                                 "--home", str(home), "--repo", str(repos[0]), "--repo", str(repos[1]))
                        self.assertEqual(0, result.returncode, result.stderr)
                        reports = json.loads(result.stdout)
                        self.assertEqual(2, len(reports))
                        for report, config in zip(reports, configs[1:]):
                            sources = {item["path"]: item for item in report["configuration_sources"]}
                            self.assertIn("error", sources[str(configs[0])])
                            self.assertEqual(config == configs[1], "error" in sources[str(config)])
                        self.assertFalse(reports[0]["configuration_current"])
                        self.assertEqual(before, {path: path.read_bytes() for path in configs})
                self.assertFalse((home / ".local").exists())

    def test_installed_check_reports_missing_disabled_mismatch_and_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                capture_output=True, check=True,
            ).stdout.strip()
            names = ("cse", "cse-sources", "cse-visualize")
            versions = {name: "local" for name in names}
            for name in names:
                result = subprocess.run(
                    [
                        sys.executable, str(ROOT / "scripts/package_inventory.py"),
                        "stage", name, str(home / f".codex/plugins/{name}"),
                        "--commit", commit, "--home", str(home),
                    ],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("enabled", json.loads(result.stdout))

            command_dir = root / "bin"
            command_dir.mkdir()
            codex = command_dir / "codex"
            codex.write_text(
                "#!/usr/bin/env python3\n"
                "import os\n"
                "print(open(os.environ['FAKE_PLUGIN_LIST']).read())\n"
            )
            codex.chmod(0o755)
            listing = root / "plugins.json"
            environment = {
                **os.environ,
                "PATH": str(command_dir) + os.pathsep + os.environ.get("PATH", ""),
                "FAKE_PLUGIN_LIST": str(listing),
            }
            check = ROOT / "scripts/check-installed.py"

            def record(name: str, *, enabled: bool = True, version: str | None = None):
                return {
                    "pluginId": f"{name}@personal", "installed": True, "enabled": enabled,
                    "version": version or versions[name],
                    "source": {"path": str(home / f".codex/plugins/{name}")},
                }

            cases = (
                ({"installed": []}, "do not match the selected configuration"),
                ({"installed": [record("cse"), record("cse-sources", enabled=False), record("cse-visualize")]}, "not enabled"),
                ({"installed": [record("cse"), record("cse-sources"), {**record("cse-visualize"), "source": {"path": str(root / "wrong")}}]}, "unexpected deployment root"),
                ({"installed": [record("cse"), record("cse-sources"), record("cse-visualize"), record("cse")]}, "missing or duplicated"),
                ({"installed": [record("cse"), record("cse-sources"), record("cse-visualize"), {**record("cse"), "pluginId": "cse@other"}]}, "do not match the selected configuration"),
                ({"installed": [record("cse"), record("cse-sources"), record("cse-visualize"), {"pluginId": "cse-experimental@personal"}]}, "unexpected CSE-family packages"),
            )
            for payload, message in cases:
                with self.subTest(message=message):
                    listing.write_text(json.dumps(payload))
                    result = subprocess.run(
                        [sys.executable, str(check), "--all", "--home", str(home)],
                        env=environment, text=True, capture_output=True, check=False,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(message, result.stderr)

            missing_source = record("cse")
            missing_source.pop("source")
            listing.write_text(json.dumps({"installed": [missing_source, record("cse-sources"), record("cse-visualize")]}))
            result = subprocess.run(
                [sys.executable, str(check), "--all", "--home", str(home)],
                env=environment, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("unexpected deployment root", result.stderr)

            listing.write_text(json.dumps({"installed": [record(name) for name in names]}))
            passed = subprocess.run(
                [sys.executable, str(check), "--all", "--home", str(home)],
                env=environment, text=True, capture_output=True, check=False,
            )
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertEqual("unverified", json.loads(passed.stdout)["active_task_loaded_state"])
            core_identity_path = home / ".codex/plugins/cse/.codex-plugin/installed.json"
            original_identity = core_identity_path.read_bytes()
            for changes, expected_message in (
                ({"sourceCommit": "0" * 40}, "source revision differs"),
                ({"enabled": True}, "identity format or metadata differs: enabled"),
            ):
                core_identity_path.write_text(json.dumps({**json.loads(original_identity), **changes}))
                result = subprocess.run(
                    [sys.executable, str(check), "--all", "--home", str(home)],
                    env=environment, text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn(expected_message, result.stderr)
                self.assertNotIn("payload altered", result.stderr)
            core_identity_path.write_bytes(original_identity)
            for selected in (("cse",), ("cse", "cse-sources"), ("cse", "cse-visualize")):
                listing.write_text(json.dumps({"installed": [record(name) for name in selected]}))
                configured = subprocess.run(
                    [
                        sys.executable, str(check), "--packages", ",".join(selected),
                        "--home", str(home),
                    ],
                    env=environment, text=True, capture_output=True, check=False,
                )
                self.assertEqual(configured.returncode, 0, configured.stderr)
            missing_core = subprocess.run(
                [sys.executable, str(check), "--packages", "cse-sources", "--home", str(home)],
                env=environment, text=True, capture_output=True, check=False,
            )
            self.assertEqual(missing_core.returncode, 2)
            self.assertIn("requires the core cse plugin", missing_core.stderr)

            listing.write_text(json.dumps({"installed": [record(name) for name in names]}))
            altered = home / ".codex/plugins/cse-sources/README.md"
            altered.write_text(altered.read_text() + "changed\n")
            rejected = subprocess.run(
                [sys.executable, str(check), "--all", "--home", str(home)],
                env=environment, text=True, capture_output=True, check=False,
            )
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("payload altered", rejected.stderr)
            identity_path = home / ".codex/plugins/cse-sources/.codex-plugin/installed.json"
            identity = json.loads(identity_path.read_text())
            inventory = subprocess.run(
                [sys.executable, "-c", "from package_inventory import runtime_tree_hash; from pathlib import Path; import sys; print(runtime_tree_hash(Path(sys.argv[1])))", str(altered.parents[0])],
                cwd=ROOT / "scripts", text=True, capture_output=True, check=True,
            ).stdout.strip()
            identity["runtimeTreeSha256"] = inventory
            identity_path.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
            source_mismatch = subprocess.run(
                [sys.executable, str(check), "--all", "--home", str(home)],
                env=environment, text=True, capture_output=True, check=False,
            )
            self.assertEqual(source_mismatch.returncode, 1)
            self.assertIn("does not match the committed source", source_mismatch.stderr)

    def test_prose_check_reads_banned_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.md"
            path.write_text("An " + "arti" + "fact" + " remains.\n")
            result = self.run_script("check_prose.py", str(path))
        self.assertEqual(result.returncode, 1)
        self.assertIn("avoid", result.stdout)

    def test_stop_checks_changed_prose_and_sourced_exemptions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_git_repository(root)
            context = root / "docs/scientific/CONTEXT.md"
            context.parent.mkdir(parents=True)
            context.write_text("# Scientific context\n")
            notebook = root / "notebook.qmd"
            notebook.write_text("Existing prose.\n")
            def invoke(event):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/cse-test-gate.py"), event],
                    input=json.dumps({"cwd": str(root), "session_id": "prose-check", "stop_hook_active": True}),
                    text=True, capture_output=True, check=True)
                return json.loads(result.stdout) if result.stdout else {}
            invoke("SessionStart")
            notebook.write_text("the pipeline is robust\n")
            blocked = invoke("Stop")
            self.assertEqual("block", blocked["decision"])
            self.assertIn("avoid 'pipeline'", blocked["reason"])
            self.assertIn("avoid 'robust'", blocked["reason"])
            notebook.write_text("`pipeline`, `pipeline_run`, and `robust.md`\n")
            self.assertNotIn("decision", invoke("Stop"))
            notebook.write_text("the model is robust.md\n")
            self.assertEqual("block", invoke("Stop")["decision"])
            context.write_text("# Scientific context\n\n| Term | Meaning | Source | Scope |\n"
                               "|---|---|---|---|\n"
                               "| pipeline | domain operation | paper:1 | * |\n"
                               "| robust | bounded estimator | paper:2 | * |\n")
            notebook.write_text("the pipeline is robust\n")
            self.assertNotIn("decision", invoke("Stop"))

    def test_prose_check_applies_scoped_rules_and_exceptions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = root / "docs/scientific/CONTEXT.md"
            context.parent.mkdir(parents=True)
            context.write_text(
                "| Avoid | Prefer | Meaning | Scope | Exceptions | Evidence |\n"
                "|---|---|---|---|---|---|\n"
                "| frozen parameter set | parameters held fixed | Preserve validation meaning. "
                "| docs/latex/sections/*.tex | frozen composition | task:608 |\n"
            )
            config = root / "config.toml"
            config.write_text(
                "[[terminology]]\n"
                'Avoid = "contact"\n'
                'Prefer = "stages"\n'
                'Meaning = "Name the extraction sequence."\n'
                'Scope = ["analyses/*/notebook.qmd"]\n'
                'Exceptions = ["MSContactor", "contact mechanics"]\n'
                'Evidence = "confirmed user correction"\n'
            )
            notebook = root / "analyses/case/notebook.qmd"
            notebook.parent.mkdir(parents=True)
            notebook.write_text(
                "Contact mechanics uses one contact followed by MSContactor.\n"
            )
            manuscript = root / "docs/latex/sections/methods.tex"
            manuscript.parent.mkdir(parents=True)
            manuscript.write_text(
                "The frozen parameter set was used; frozen composition was retained.\n"
            )
            outside = root / "notes.md"
            outside.write_text("contact and frozen parameter set\n")

            result = self.run_script(
                "check_prose.py",
                str(notebook),
                str(manuscript),
                str(outside),
                "--config",
                str(config),
                "--context",
                str(context),
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("avoid 'contact' → stages", result.stdout)
        self.assertEqual(result.stdout.count("avoid 'contact'"), 1)
        self.assertIn(
            "avoid 'frozen parameter set' → parameters held fixed",
            result.stdout,
        )
        self.assertEqual(result.stdout.count("avoid 'contact'"), 1)
        self.assertNotIn("notes.md", result.stdout)

    def test_prose_check_rejects_overlapping_authorities(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = root / "docs/scientific/CONTEXT.md"
            context.parent.mkdir(parents=True)
            context.write_text(
                "| Avoid | Prefer | Meaning | Scope | Exceptions | Evidence |\n"
                "|---|---|---|---|---|---|\n"
                "| contact | stages | Repository meaning. | analyses/*/notebook.qmd |  | repo |\n"
            )
            config = root / "config.toml"
            config.write_text(
                "[[terminology]]\n"
                'Avoid = "contact"\n'
                'Prefer = "stages"\n'
                'Meaning = "Personal meaning."\n'
                'Scope = ["analyses/*/notebook.qmd"]\n'
                'Exceptions = []\n'
                'Evidence = "user"\n'
            )
            draft = root / "analyses/case/notebook.qmd"
            draft.parent.mkdir(parents=True)
            draft.write_text("contact\n")
            result = self.run_script(
                "check_prose.py",
                str(draft),
                "--config",
                str(config),
                "--context",
                str(context),
            )
            context.write_text(
                "| Avoid | Prefer | Meaning | Scope | Exceptions | Evidence |\n"
                "|---|---|---|---|---|---|\n"
                "| contact | stages | Repository meaning. | docs/latex/*.tex |  | repo |\n"
            )
            draft.write_text("stages\n")
            resolved = self.run_script(
                "check_prose.py",
                str(draft),
                "--config",
                str(config),
                "--context",
                str(context),
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("terminology conflict", result.stdout)
        self.assertEqual(resolved.returncode, 0, resolved.stdout)

    def test_bibliography_sync_and_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "export.bib"
            destination = root / "docs" / "references.bib"
            source.write_text("@article{case, title={Reference}}\n")
            copied = self.run_script("extensions/cse-sources/scripts/sync_bibliography.py", str(source), str(destination))
            checked = self.run_script(
                "extensions/cse-sources/scripts/sync_bibliography.py", str(source), str(destination), "--check"
            )
        self.assertEqual(copied.returncode, 0, copied.stderr)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_marketplace_registration_preserves_other_plugins(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "marketplace.json"
            path.write_text(
                json.dumps(
                    {
                        "name": "personal",
                        "interface": {"displayName": "Mine"},
                        "plugins": [{"name": "existing"}, {"name": "scientific-codex"}],
                    }
                )
            )
            result = self.run_script("register_marketplace.py", "--marketplace", str(path))
            data = json.loads(path.read_text())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["interface"]["displayName"], "Mine")
        self.assertEqual([entry["name"] for entry in data["plugins"]], ["existing", "cse", "cse-sources", "cse-visualize"])

    def test_visual_qa_classifies_text_and_graphic_collisions(self):
        fixture_root = ROOT / "tests/fixtures/latex-visual-qa"
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory)
            tex_cache = build / "tex-cache"
            tex_cache.mkdir()
            environment = os.environ | {
                "TEXMFVAR": str(tex_cache),
                "TEXMFCACHE": str(tex_cache),
            }
            results = {}
            for name in ("clean", "text-overlap", "text-graphic-overlap"):
                compiled = subprocess.run(
                    [
                        "lualatex",
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        f"-output-directory={build}",
                        str(fixture_root / f"{name}.tex"),
                    ],
                    env=environment,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(compiled.returncode, 0, compiled.stdout[-2000:])
                arguments = [
                    "extensions/cse-visualize/scripts/latex_visual_qa.py",
                    str(build / f"{name}.pdf"),
                    "--profile",
                    "article",
                    "--output-dir",
                    str(build / f"qa-{name}"),
                ]
                if name == "text-graphic-overlap":
                    arguments.append("--warnings-as-errors")
                results[name] = self.run_script(*arguments)

            report = json.loads((build / "qa-text-overlap/report.json").read_text())
            graphic_report = json.loads(
                (build / "qa-text-graphic-overlap/report.json").read_text()
            )
        self.assertEqual(results["clean"].returncode, 0, results["clean"].stderr)
        self.assertEqual(results["text-overlap"].returncode, 1, results["text-overlap"].stderr)
        self.assertEqual(
            results["text-graphic-overlap"].returncode,
            1,
            results["text-graphic-overlap"].stderr,
        )
        self.assertIn("text_overlap", {issue["code"] for issue in report["issues"]})
        self.assertIn(
            "text_graphic_overlap",
            {issue["code"] for issue in graphic_report["issues"]},
        )

    def test_quarto_scaffold_is_additive_and_refuses_collisions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_git_repository(root)
            script = ROOT / "extensions/cse-visualize/assets/project/quarto/scaffold.sh"
            analysis = root / "analyses" / "case"
            analysis.mkdir(parents=True)
            marker = analysis / "results.csv"
            marker.write_bytes(b"retained\n")
            retained = marker.read_bytes()
            created = subprocess.run(
                ["bash", str(script), str(analysis)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            for relative in (
                ".gitignore", "_quarto.yml", "_quarto-promoted-pdf.yml",
                "promoted-pdf-header.tex", "render.sh", "notebook.qmd",
            ):
                self.assertTrue((analysis / relative).is_file(), relative)
            self.assertIn("enabled: false", (analysis / "notebook.qmd").read_text())
            self.assertIn("html:", (analysis / "_quarto.yml").read_text())
            self.assertIn("pdf-engine: lualatex", (analysis / "_quarto-promoted-pdf.yml").read_text())
            self.assertIn("include-in-header", (analysis / "_quarto-promoted-pdf.yml").read_text())
            self.assertEqual(retained, marker.read_bytes())

            header_check = subprocess.run(
                ["git", "check-ignore", "--no-index", "promoted-pdf-header.tex"],
                cwd=analysis, text=True, capture_output=True, check=False,
            )
            generated_check = subprocess.run(
                ["git", "check-ignore", "--no-index", "notebook.tex"],
                cwd=analysis, text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(header_check.returncode, 0, header_check.stdout)
            self.assertEqual(generated_check.returncode, 0, generated_check.stdout)

            scaffold_files = (
                ".gitignore", "_quarto.yml", "_quarto-promoted-pdf.yml",
                "promoted-pdf-header.tex", "render.sh", "notebook.qmd",
            )
            before_refusal = {
                relative: (analysis / relative).read_bytes()
                for relative in (*scaffold_files, "results.csv")
            }
            refused = subprocess.run(
                ["bash", str(script), str(analysis)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(refused.returncode, 1)
            self.assertIn("scaffold-owned", refused.stderr)
            after_refusal = {
                relative: (analysis / relative).read_bytes()
                for relative in (*scaffold_files, "results.csv")
            }
            self.assertEqual(before_refusal, after_refusal)

            notebook_collision = root / "analyses" / "notebook-collision"
            notebook_collision.mkdir()
            (notebook_collision / "notebook.qmd").write_text("existing\n")
            refused_notebook = subprocess.run(
                ["bash", str(script), str(notebook_collision)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(refused_notebook.returncode, 1)
            self.assertIn("notebook.qmd", refused_notebook.stderr)
            self.assertFalse((notebook_collision / ".gitignore").exists())

    def test_quarto_release_entrypoint_isolates_lualatex_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            runtime_parent = project / "runtime"
            inherited_cache = project / "inherited-cache"
            texmf_config = project / "texmf-config"
            proxy_directory = project / "bin"
            runtime_parent.mkdir()
            inherited_cache.mkdir()
            inherited_cache.chmod(0o555)
            texmf_config.mkdir()
            proxy_directory.mkdir()
            shutil.copy2(ROOT / "extensions/cse-visualize/assets/project/quarto/_quarto.yml", project)
            shutil.copy2(ROOT / "extensions/cse-visualize/assets/project/quarto/render.sh", project)
            for name in ("_quarto-promoted-pdf.yml", "promoted-pdf-header.tex"):
                shutil.copy2(ROOT / "extensions/cse-visualize/assets/project/quarto" / name, project)
            real_quarto = shutil.which("quarto")
            self.assertIsNotNone(real_quarto)
            proxy = proxy_directory / "quarto"
            proxy.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$TEXMFVAR\" \"$TEXMFCACHE\" "
                "\"$QUARTO_CACHE_DIR\" \"$DENO_DIR\" \"$XDG_CACHE_HOME\" "
                "\"$HOME\" \"$TEXMFCONFIG\" "
                "\"${@: -1}\" > \"$CSE_RENDER_ENV_LOG\"\n"
                "exec \"$CSE_REAL_QUARTO\" \"$@\"\n"
            )
            proxy.chmod(0o755)
            (project / "document.qmd").write_text(
                "---\ntitle: Nonexecuting notebook\n---\n\n"
                "Fixed temperature: $T_a = 22\\,^\\circ\\mathrm{C}$.\n\n"
                "```{python}\nfrom pathlib import Path\n"
                "Path('model-ran').write_text('unsafe')\n```\n"
            )
            environment = os.environ | {
                "PATH": f"{proxy_directory}{os.pathsep}{os.environ['PATH']}",
                "TMPDIR": str(runtime_parent),
                "TEXMFVAR": str(inherited_cache),
                "TEXMFCACHE": str(inherited_cache),
                "TEXMFCONFIG": str(texmf_config),
                "CSE_REAL_QUARTO": real_quarto,
                "CSE_RENDER_ENV_LOG": str(project / "render-env"),
            }
            tinytex_root = Path(
                subprocess.run(
                    ["kpsewhich", "-var-value=TEXMFROOT"],
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout.strip()
            )
            package_database = tinytex_root / "tlpkg/texlive.tlpdb"
            package_database_before = package_database.read_bytes()
            rendered = subprocess.run(
                ["bash", "render.sh", "document.qmd", "--profile", "promoted-pdf", "--to", "pdf"],
                cwd=project,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            runtime_values = (project / "render-env").read_text().splitlines()

            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertTrue((project / "builds/document.pdf").is_file())
            self.assertFalse((project / "model-ran").exists())
            self.assertEqual(runtime_values[-1], "--no-execute")
            self.assertEqual(runtime_values[5], environment["HOME"])
            self.assertEqual(runtime_values[6], str(texmf_config))
            self.assertEqual(runtime_values[0], runtime_values[1])
            runtime_root = Path(runtime_values[0]).parent
            self.assertEqual(runtime_root.parent, runtime_parent)
            self.assertTrue(
                all(Path(value).parent == runtime_root for value in runtime_values[:5])
            )
            self.assertFalse(runtime_root.exists())
            self.assertEqual(list(inherited_cache.iterdir()), [])

            (project / "document.qmd").write_text(
                "---\nformat:\n  pdf:\n    include-in-header:\n"
                "      text: |\n        \\usepackage{cse-package-does-not-exist}\n"
                "---\n\nMissing package check.\n"
            )
            missing_package = subprocess.run(
                ["bash", "render.sh", "document.qmd"],
                cwd=project,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            failed_runtime_root = Path(
                (project / "render-env").read_text().splitlines()[0]
            ).parent
            self.assertNotEqual(missing_package.returncode, 0)
            self.assertIn(
                "cse-package-does-not-exist.sty",
                missing_package.stdout + missing_package.stderr,
            )
            self.assertFalse(failed_runtime_root.exists())
            self.assertEqual(package_database.read_bytes(), package_database_before)

            (project / "document.qmd").write_text(
                "---\nformat: pdf\n---\n\n\\notacommandfromcse\n"
            )
            invalid_source = subprocess.run(
                ["bash", "render.sh", "document.qmd"],
                cwd=project,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            failed_runtime_root = Path(
                (project / "render-env").read_text().splitlines()[0]
            ).parent
            self.assertNotEqual(invalid_source.returncode, 0)
            self.assertIn(
                "Undefined control sequence",
                invalid_source.stdout + invalid_source.stderr,
            )
            self.assertFalse(failed_runtime_root.exists())

    def test_live_sync_restores_previous_deployment_when_registration_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            home = root / "home"
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", ".runs"))
            (source / "scripts/validate.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
            (source / "scripts/register_marketplace.py").write_text("raise SystemExit(9)\n")
            validator = root / "validator.py"
            validator.write_text("import sys\nraise SystemExit(0 if len(sys.argv) == 2 else 8)\n")
            subprocess.run(["git", "init", "-q"], cwd=source, check=True)
            subprocess.run(["git", "add", "-A"], cwd=source, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"],
                cwd=source,
                check=True,
            )
            deployed = home / ".codex/plugins/cse"
            deployed.mkdir(parents=True)
            (deployed / "previous.txt").write_text("preserve\n")
            environment = os.environ | {
                "HOME": str(home),
                "CSE_SKILL_VALIDATOR": str(validator),
            }
            result = subprocess.run(
                ["bash", str(source / "scripts/sync-live.sh"), "--validate"],
                cwd=source,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            preserved = (deployed / "previous.txt").read_text()

        self.assertEqual(result.returncode, 1)
        self.assertEqual(preserved, "preserve\n")

    def test_live_sync_removes_identified_legacy_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            home = root / "home"
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", ".runs"))
            (source / "scripts/validate.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
            validator = root / "validator.py"
            validator.write_text("raise SystemExit(0)\n")
            (source / ".runs/cooling-fit/run-1").mkdir(parents=True)
            (source / ".runs/cooling-fit/run-1/events.jsonl").write_text("source-only\n")
            subprocess.run(["git", "init", "-q"], cwd=source, check=True)
            subprocess.run(["git", "add", "-A"], cwd=source, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"],
                cwd=source,
                check=True,
            )
            legacy = home / ".codex/plugins/scientific-codex"
            (legacy / ".codex-plugin").mkdir(parents=True)
            (legacy / ".codex-plugin/plugin.json").write_text(
                json.dumps({"name": "scientific-codex"})
            )
            environment = os.environ | {
                "HOME": str(home),
                "CSE_SKILL_VALIDATOR": str(validator),
            }
            result = subprocess.run(
                ["bash", str(source / "scripts/sync-live.sh"), "--validate"],
                cwd=source,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            identified_removed = not legacy.exists()
            unexpected = home / ".codex/plugins/scientific-codex"
            unexpected.mkdir()
            (unexpected / "keep.txt").write_text("user directory\n")
            preserved_result = subprocess.run(
                ["bash", str(source / "scripts/sync-live.sh"), "--validate"],
                cwd=source,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            preserved = (unexpected / "keep.txt").read_text()
            deployed = home / ".codex/plugins/cse"
            excluded = tuple(
                (deployed / relative).exists()
                for relative in (
                    "examples", "cse-pi-harness", "docs", "evaluation", ".runs",
                    "scripts/cooling_fit_benchmark.py", "hooks/hooks.json",
                )
            )
            project_hooks_installed = (deployed / "assets/codex/hooks.json").is_file()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(identified_removed)
        self.assertEqual(preserved_result.returncode, 0, preserved_result.stderr)
        self.assertEqual(preserved, "user directory\n")
        self.assertFalse(any(excluded))
        self.assertTrue(project_hooks_installed)

    def test_every_family_failure_checkpoint_is_atomic_for_first_install_and_upgrade(self):
        packages = ("cse", "cse-sources", "cse-visualize")
        checkpoints = tuple(
            f"{phase}:{side}:{name}"
            for phase in ("validate", "stage", "deploy", "register")
            for side in ("before", "after")
            for name in packages
        ) + ("register-final:before", "register-final:after")

        def tree(path: Path):
            return {
                item.relative_to(path).as_posix(): item.read_bytes()
                for item in path.rglob("*") if item.is_file()
            } if path.is_dir() else None

        def state(home: Path):
            return {
                **{name: tree(home / f".codex/plugins/{name}") for name in packages},
                "legacy": tree(home / ".codex/plugins/scientific-codex"),
                "marketplace": (
                    home / ".agents/plugins/marketplace.json"
                ).read_bytes() if (home / ".agents/plugins/marketplace.json").is_file() else None,
            }

        def seed_verified_legacy(home: Path):
            legacy = home / ".codex/plugins/scientific-codex/.codex-plugin"
            legacy.mkdir(parents=True)
            (legacy / "plugin.json").write_text(json.dumps({"name": "scientific-codex"}))
            marketplace = home / ".agents/plugins/marketplace.json"
            marketplace.parent.mkdir(parents=True, exist_ok=True)
            data = json.loads(marketplace.read_text()) if marketplace.is_file() else {
                "name": "personal", "plugins": []
            }
            data["plugins"] = [
                *data["plugins"], {"name": "scientific-codex"}
            ]
            marketplace.write_text(json.dumps(data))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            shutil.copytree(
                ROOT, source,
                ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", ".runs"),
            )
            (source / "scripts/validate.sh").write_text(
                "#!/usr/bin/env bash\n"
                "case \"${CSE_FAIL_AT:-}\" in validate:*) exit 9;; esac\n"
                "exit 0\n"
            )
            (source / "scripts/validate.sh").chmod(0o755)
            validator = root / "validator.py"
            validator.write_text("raise SystemExit(0)\n")
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
            subprocess.run(["git", "add", "-A"], cwd=source, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"],
                cwd=source, check=True,
            )

            def invoke(home: Path, checkpoint: str | None = None):
                environment = os.environ | {
                    "HOME": str(home), "CSE_SKILL_VALIDATOR": str(validator),
                }
                if checkpoint:
                    environment["CSE_FAIL_AT"] = checkpoint
                return subprocess.run(
                    ["bash", "scripts/sync-live.sh", "--validate"], cwd=source,
                    env=environment, text=True, capture_output=True, check=False,
                )

            prior = root / "prior"
            installed = invoke(prior)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            seed_verified_legacy(prior)
            prior_state = state(prior)
            self.assertIsNotNone(prior_state["legacy"])
            self.assertIn(b'"scientific-codex"', prior_state["marketplace"])

            for checkpoint in checkpoints:
                with self.subTest(mode="first", checkpoint=checkpoint):
                    home = root / "first" / checkpoint.replace(":", "-")
                    seed_verified_legacy(home)
                    marketplace = home / ".agents/plugins/marketplace.json"
                    data = json.loads(marketplace.read_text())
                    data["plugins"].insert(0, {"name": "other"})
                    marketplace.write_text(json.dumps(data))
                    before = state(home)
                    self.assertIsNotNone(before["legacy"])
                    self.assertIn(b'"scientific-codex"', before["marketplace"])
                    result = invoke(home, checkpoint)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(state(home), before)

                with self.subTest(mode="upgrade", checkpoint=checkpoint):
                    home = root / "upgrade" / checkpoint.replace(":", "-")
                    shutil.copytree(prior, home)
                    result = invoke(home, checkpoint)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(state(home), prior_state)


if __name__ == "__main__":
    unittest.main()
