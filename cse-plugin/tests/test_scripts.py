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
                        "plugins": [{"name": "existing"}],
                    }
                )
            )
            result = self.run_script("register_marketplace.py", "--marketplace", str(path))
            data = json.loads(path.read_text())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["interface"]["displayName"], "Mine")
        self.assertEqual([entry["name"] for entry in data["plugins"]], ["existing", "scientific-codex"])

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
            deployed = home / ".codex/plugins/scientific-codex"
            deployed.mkdir(parents=True)
            (deployed / "previous.txt").write_text("preserve\n")
            environment = os.environ | {
                "HOME": str(home),
                "SCIENTIFIC_CODEX_DEPLOY_ROOT": str(deployed),
                "SCIENTIFIC_CODEX_PLUGIN_VALIDATOR": str(validator),
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
