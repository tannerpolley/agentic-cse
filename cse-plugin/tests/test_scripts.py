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

    def test_prose_check_rejects_default_forbidden_word(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.md"
            path.write_text("An " + "arti" + "fact" + " remains.\n")
            result = self.run_script("check_prose.py", str(path))
        self.assertEqual(result.returncode, 1)
        self.assertIn("forbidden word", result.stdout)

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
