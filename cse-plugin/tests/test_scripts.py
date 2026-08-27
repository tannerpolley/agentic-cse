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
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *arguments],
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
        self.assertEqual(report["executable_removal_to_addition_ratio"], 0.5)

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
        self.assertIn("executable removal/addition ratio: not applicable", result.stdout)
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

    def test_cse_review_stop_hook_is_opt_in_and_single_shot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repo"
            repository.mkdir()
            self.initialize_git_repository(repository)
            plugin = root / "plugin"
            scripts = plugin / "scripts"
            scripts.mkdir(parents=True)
            accounting = scripts / "change_accounting.py"
            hook = ROOT / "scripts/cse-review-stop.py"
            environment = {**os.environ, "PLUGIN_ROOT": str(plugin)}

            def invoke(*, active=False, cwd=repository):
                return subprocess.run(
                    [sys.executable, str(hook)],
                    input=json.dumps({"cwd": str(cwd), "stop_hook_active": active}),
                    env=environment,
                    text=True,
                    capture_output=True,
                    check=False,
                )

            accounting.write_text("raise SystemExit(9)\n")
            outside = root / "outside"
            outside.mkdir()
            self.assertEqual(invoke(cwd=outside).stdout, "")
            self.assertEqual(invoke().stdout, "")

            (repository / "AGENTS.md").write_text(
                "Repository Profile: scientific-computing\n"
            )
            self.commit_all(repository, "baseline")
            self.assertEqual(invoke(active=True).stdout, "")

            report = {
                "categories": {
                    "executable": {"files": 0},
                    "tests": {"files": 0},
                },
                "files": [{"category": "documents", "path": "README.md"}],
            }
            accounting.write_text(
                "import json\nprint(json.dumps(" + repr(report) + "))\n"
            )
            self.assertEqual(invoke().stdout, "")

            report["files"] = [{"category": "other", "path": "solver.yaml"}]
            accounting.write_text(
                "import json\nprint(json.dumps(" + repr(report) + "))\n"
            )
            config_reminder = json.loads(invoke().stdout)
            self.assertEqual(config_reminder["decision"], "block")

            report["categories"]["executable"]["files"] = 1
            report["files"] = [{"category": "executable", "path": "src/model.py"}]
            accounting.write_text(
                "import json\nprint(json.dumps(" + repr(report) + "))\n"
            )
            reminder = json.loads(invoke().stdout)
            self.assertEqual(reminder["decision"], "block")
            self.assertIn("Apply CSE Review", reminder["reason"])

            accounting.write_text("raise SystemExit(9)\n")
            warning = json.loads(invoke().stdout)
            self.assertIn("skipped", warning["systemMessage"])

            accounting.write_text(
                'print(\'{"files":[null],"categories":{"executable":{"files":0},'
                '"tests":{"files":0}}}\')\n'
            )
            malformed = json.loads(invoke().stdout)
            self.assertIn("invalid data", malformed["systemMessage"])

            (repository / "src").mkdir()
            (repository / "src/model.py").write_text("result = 1\n")
            integrated = subprocess.run(
                [sys.executable, str(hook)],
                input=json.dumps({"cwd": str(repository), "stop_hook_active": False}),
                env={**os.environ, "PLUGIN_ROOT": str(ROOT)},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(json.loads(integrated.stdout)["decision"], "block")

    def test_installed_check_reports_missing_disabled_mismatch_and_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            deployed = root / "deployed"
            for relative in (
                ".codex-plugin/plugin.json",
                "hooks/hooks.json",
                "scripts/change_accounting.py",
                "scripts/check-installed.py",
                "scripts/check_prose.py",
                "scripts/cse-review-stop.py",
            ):
                destination = deployed / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            for source in (ROOT / "skills").glob("*/SKILL.md"):
                destination = deployed / source.relative_to(ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

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
                "CSE_DEPLOY_ROOT": str(deployed),
                "FAKE_PLUGIN_LIST": str(listing),
            }
            check = ROOT / "scripts/check-installed.py"

            cases = (
                ({"installed": []}, "not installed"),
                ({"installed": [{
                    "pluginId": "cse@personal", "installed": True,
                    "enabled": False, "version": "1.1.0",
                    "source": {"path": str(deployed)},
                }]}, "disabled"),
                ({"installed": [{
                    "pluginId": "cse@personal", "installed": True,
                    "enabled": True, "version": "1.0.0",
                    "source": {"path": str(deployed)},
                }]}, "expected '1.1.0'"),
            )
            for payload, message in cases:
                with self.subTest(message=message):
                    listing.write_text(json.dumps(payload))
                    result = subprocess.run(
                        [sys.executable, str(check)], env=environment, text=True,
                        capture_output=True, check=False,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(message, result.stderr)

            listing.write_text(json.dumps({"installed": [{
                "pluginId": "cse@personal", "installed": True,
                "enabled": True, "version": "1.1.0",
                "source": {"path": str(deployed)},
            }]}))
            result = subprocess.run(
                [sys.executable, str(check)], env=environment, text=True,
                capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("CSE installed check passed", result.stdout)

    def test_prose_check_rejects_default_forbidden_word(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.md"
            path.write_text("An " + "arti" + "fact" + " remains.\n")
            result = self.run_script("check_prose.py", str(path))
        self.assertEqual(result.returncode, 1)
        self.assertIn("forbidden word", result.stdout)

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
        self.assertIn("avoid 'contact' → prefer 'stages'", result.stdout)
        self.assertEqual(result.stdout.count("avoid 'contact'"), 1)
        self.assertIn(
            "avoid 'frozen parameter set' → prefer 'parameters held fixed'",
            result.stdout,
        )
        self.assertNotIn("MSContactor", result.stdout)
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
            copied = self.run_script("sync_bibliography.py", str(source), str(destination))
            checked = self.run_script(
                "sync_bibliography.py", str(source), str(destination), "--check"
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
        self.assertEqual([entry["name"] for entry in data["plugins"]], ["existing", "cse"])

    def test_visual_qa_classifies_text_and_graphic_collisions(self):
        fixture_root = ROOT / "tests/fixtures/latex-visual-qa"
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory)
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
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(compiled.returncode, 0, compiled.stdout[-2000:])
                arguments = [
                    "latex_visual_qa.py",
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

    def test_quarto_release_entrypoint_does_not_execute_document_python(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            shutil.copy2(ROOT / "assets/project/quarto/_quarto.yml", project)
            shutil.copy2(ROOT / "assets/project/quarto/render.sh", project)
            (project / "document.qmd").write_text(
                "---\nformat: html\n---\n\n"
                "```{python}\nfrom pathlib import Path\n"
                "Path('model-ran').write_text('unsafe')\n```\n"
            )
            rendered = subprocess.run(
                ["bash", "render.sh", "document.qmd"],
                cwd=project,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertTrue((project / "builds/document.html").is_file())
            self.assertFalse((project / "model-ran").exists())

    def test_live_sync_restores_previous_deployment_when_registration_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            home = root / "home"
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", ".venv"))
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
                "CSE_DEPLOY_ROOT": str(deployed),
                "CSE_PLUGIN_VALIDATOR": str(validator),
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
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", ".venv"))
            (source / "scripts/validate.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
            validator = root / "validator.py"
            validator.write_text("raise SystemExit(0)\n")
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
                "CSE_DEPLOY_ROOT": str(home / ".codex/plugins/cse"),
                "CSE_PLUGIN_VALIDATOR": str(validator),
            }
            result = subprocess.run(
                ["bash", str(source / "scripts/sync-live.sh"), "--validate"],
                cwd=source,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(legacy.exists())
        deployed = home / ".codex/plugins/cse"
        self.assertFalse((deployed / "examples").exists())
        self.assertFalse((deployed / "cse-pi-harness").exists())


if __name__ == "__main__":
    unittest.main()
