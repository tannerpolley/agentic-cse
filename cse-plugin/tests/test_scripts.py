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
                if name == "clean":
                    arguments.extend(("--baseline", str(build / "clean.pdf")))
                elif name == "text-graphic-overlap":
                    arguments.append("--warnings-as-errors")
                results[name] = self.run_script(*arguments)

            report = json.loads((build / "qa-text-overlap/report.json").read_text())
            graphic_report = json.loads(
                (build / "qa-text-graphic-overlap/report.json").read_text()
            )
            clean_report = json.loads((build / "qa-clean/report.json").read_text())

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
        self.assertEqual(graphic_report["checks"]["vector_clearance"], "complete")
        self.assertEqual(clean_report["baseline"]["changed_pages"], [])

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


if __name__ == "__main__":
    unittest.main()
