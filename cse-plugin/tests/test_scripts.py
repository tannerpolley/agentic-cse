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
INVENTORY = ROOT / "scripts/package_inventory.py"


class PackageLifecycleTests(unittest.TestCase):
    def run_inventory(self, *args: str, env: dict | None = None):
        return subprocess.run([sys.executable, str(INVENTORY), *args], text=True, capture_output=True, env=env, check=False)

    def test_staging_and_identity_cover_exact_three_package_payloads(self):
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
        expected = {
            "cse": ["setup", "research", "diagnose", "design", "build", "analyze", "review", "summarize", "write"],
            "cse-sources": ["zotero", "mathpix", "data", "digitize"],
            "cse-visualize": ["plot", "tikz", "pgfplots", "latex", "quarto", "revealjs", "beamer"],
        }
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            for name, skills in expected.items():
                staged = Path(directory) / name
                result = self.run_inventory("stage", name, str(staged), "--commit", commit, "--home", str(home))
                self.assertEqual(result.returncode, 0, result.stderr)
                identity = json.loads(result.stdout)
                self.assertEqual(identity["payloadSkills"], skills)
                self.assertEqual(identity["sourceCommit"], commit)
                verified = self.run_inventory("verify", name, str(staged), "--commit", commit, "--home", str(home))
                self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_marketplace_registration_is_idempotent_and_retires_legacy_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            marketplace = Path(directory) / "marketplace.json"
            marketplace.write_text(json.dumps({"name": "personal", "plugins": [{"name": "other"}, {"name": "scientific-codex"}]}))
            for _ in range(2):
                result = subprocess.run([sys.executable, str(ROOT / "scripts/register_marketplace.py"), "--marketplace", str(marketplace)], text=True, capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
            names = [entry["name"] for entry in json.loads(marketplace.read_text())["plugins"]]
        self.assertEqual(names, ["other", "cse", "cse-sources", "cse-visualize"])

    def test_failure_injection_does_not_publish_a_partial_marketplace(self):
        with tempfile.TemporaryDirectory() as directory:
            marketplace = Path(directory) / "marketplace.json"
            original = b'{"name":"personal","plugins":[{"name":"other"}]}'
            marketplace.write_bytes(original)
            environment = os.environ | {"CSE_FAIL_AT": "register:after:cse-sources"}
            result = subprocess.run([sys.executable, str(ROOT / "scripts/register_marketplace.py"), "--marketplace", str(marketplace)], env=environment, text=True, capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(marketplace.read_bytes(), original)

    def test_sources_bibliography_sync_remains_explicit_and_read_only_checkable(self):
        script = ROOT / "extensions/cse-sources/scripts/sync_bibliography.py"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.bib"
            target = Path(directory) / "docs/references.bib"
            source.write_text("@article{case, title={Reference}}\n")
            copied = subprocess.run([sys.executable, str(script), str(source), str(target)], text=True, capture_output=True, check=False)
            checked = subprocess.run([sys.executable, str(script), str(source), str(target), "--check"], text=True, capture_output=True, check=False)
        self.assertEqual(copied.returncode, 0, copied.stderr)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_sync_rollback_restores_an_upgrade_and_preserves_unexpected_legacy_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            home = Path(directory) / "home"
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".runs"))
            (source / "scripts/validate.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
            (source / "scripts/validate.sh").chmod(0o755)
            validator = Path(directory) / "validator.py"
            validator.write_text("raise SystemExit(0)\n")
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
            subprocess.run(["git", "add", "-A"], cwd=source, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"], cwd=source, check=True)
            legacy = home / ".codex/plugins/scientific-codex/.codex-plugin"
            legacy.mkdir(parents=True)
            (legacy / "plugin.json").write_text(json.dumps({"name": "scientific-codex"}))
            environment = os.environ | {"HOME": str(home), "CSE_PLUGIN_VALIDATOR": str(validator)}
            installed = subprocess.run(["bash", "scripts/sync-live.sh", "--validate"], cwd=source, env=environment, text=True, capture_output=True, check=False)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            self.assertFalse(legacy.parent.exists())
            marketplace = home / ".agents/plugins/marketplace.json"
            before_marketplace = marketplace.read_bytes()
            before_identities = {
                name: (home / f".codex/plugins/{name}/.codex-plugin/installed.json").read_bytes()
                for name in ("cse", "cse-sources", "cse-visualize")
            }
            failed = subprocess.run(["bash", "scripts/sync-live.sh", "--validate"], cwd=source, env=environment | {"CSE_FAIL_AT": "deploy:after:cse-visualize"}, text=True, capture_output=True, check=False)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(marketplace.read_bytes(), before_marketplace)
            self.assertEqual({
                name: (home / f".codex/plugins/{name}/.codex-plugin/installed.json").read_bytes()
                for name in before_identities
            }, before_identities)
            unexpected = home / ".codex/plugins/scientific-codex"
            unexpected.mkdir()
            (unexpected / "keep.txt").write_text("user directory\n")
            preserved = subprocess.run(["bash", "scripts/sync-live.sh", "--validate"], cwd=source, env=environment, text=True, capture_output=True, check=False)
            self.assertEqual(preserved.returncode, 0, preserved.stderr)
            self.assertEqual((unexpected / "keep.txt").read_text(), "user directory\n")


if __name__ == "__main__":
    unittest.main()
