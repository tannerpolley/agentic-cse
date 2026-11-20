from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_IGNORE = shutil.ignore_patterns(".git", ".runs", "__pycache__", ".pytest_cache")


class InstallationBehaviorTests(unittest.TestCase):
    def git_fixture(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"], cwd=root, check=True)

    def test_sync_installs_from_repository_marketplace_and_rolls_back_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            source = repository / "cse-plugin"
            shutil.copytree(ROOT, source, ignore=PLUGIN_IGNORE)
            with (source / ".gitignore").open("a") as ignore:
                ignore.write("\n.idea/\n")
            validate = source / "scripts/validate.sh"
            validate.write_text("#!/usr/bin/env bash\nexit 0\n")
            validate.chmod(0o755)
            runtime = repository / "cse-zotero"
            (runtime / "src/zotero_companion" / "schemas/linkml").mkdir(parents=True)
            (runtime / "examples").mkdir()
            (runtime / "pyproject.toml").write_text(
                "[build-system]\nrequires = [\"setuptools>=68\"]\nbuild-backend = \"setuptools.build_meta\"\n"
                "[project]\nname = \"cse-zotero\"\nversion = \"1.0.0\"\nrequires-python = \">=3.11\"\n"
                "[project.scripts]\ncse-zotero = \"zotero_companion.cli:main\"\n"
                "zotero-companion = \"zotero_companion.cli:main\"\n"
                "[tool.setuptools.packages.find]\nwhere = [\"src\"]\n"
            )
            (runtime / "src/zotero_companion/__init__.py").write_text("")
            (runtime / "src/zotero_companion/cli.py").write_text(
                "import json\nimport sys\n\n"
                "def main():\n"
                "    print(json.dumps({'ok': True, 'command': sys.argv[1] if len(sys.argv) > 1 else ''}))\n"
            )
            (runtime / "src/zotero_companion/schemas/linkml/thermophysical.yaml").write_text("id: controlled\n")
            (runtime / "examples/core-records.yaml").write_text("records: []\n")
            (runtime / "examples/thermophysical-record.yaml").write_text("records: []\n")
            self.git_fixture(repository)
            home = root / "home"
            old_runtime = home / ".local/share/cse/zotero"
            old_runtime.mkdir(parents=True)
            (old_runtime / "previous.txt").write_text("previous runtime\n")
            agent_build = old_runtime / "zotero-connector-agent/cse-agent-build.json"
            agent_build.parent.mkdir()
            agent_build.write_text('{"module_revision": 20}\n')
            old_bin = home / ".local/bin"
            old_bin.mkdir(parents=True)
            for command in ("cse-zotero", "zotero-companion"):
                (old_bin / command).write_text(f"previous {command}\n")
            command_dir = root / "bin"
            command_dir.mkdir()
            (command_dir / "codex").write_text(textwrap.dedent(
                """
                #!/usr/bin/env python3
                import json
                import os
                import shutil
                import sys
                from pathlib import Path

                home = Path(os.environ["HOME"])
                state_path = home / ".codex/fake-state.json"
                state = json.loads(state_path.read_text()) if state_path.exists() else {"marketplaces": {}, "installed": []}
                args = [token for token in sys.argv[1:] if token != "--json"]

                if args == ["plugin", "marketplace", "list"]:
                    print(json.dumps({"marketplaces": [{"name": name, "root": root} for name, root in state["marketplaces"].items()]}))
                    raise SystemExit
                if args == ["plugin", "list"]:
                    print(json.dumps({"installed": state["installed"]}))
                    raise SystemExit
                if args[:3] == ["plugin", "marketplace", "add"]:
                    source = str(Path(args[3]).resolve())
                    name = json.loads((Path(source) / ".claude-plugin/marketplace.json").read_text())["name"]
                    if state["marketplaces"].get(name, source) != source:
                        raise SystemExit(f"marketplace '{name}' is already added from a different source")
                    state["marketplaces"][name] = source
                elif args[:3] == ["plugin", "marketplace", "remove"]:
                    state["marketplaces"].pop(args[3])
                elif args[:2] in (["plugin", "add"], ["plugin", "remove"]):
                    name, marketplace = args[2].split("@")
                    cache = home / ".codex/plugins/cache" / marketplace / name / "local"
                    shutil.rmtree(cache, ignore_errors=True)
                    state["installed"] = [item for item in state["installed"] if item["pluginId"] != args[2]]
                    if args[1] == "add":
                        root = Path(state["marketplaces"][marketplace])
                        catalog = json.loads((root / ".claude-plugin/marketplace.json").read_text())
                        origin = root / next(item for item in catalog["plugins"] if item["name"] == name)["source"]
                        shutil.copytree(origin, cache)
                        state["installed"].append({
                            "pluginId": args[2], "installed": True, "enabled": True,
                            "source": {"source": "local", "path": str(origin)},
                            "marketplaceSource": {"sourceType": "local", "source": str(root)},
                        })
                else:
                    raise SystemExit("unsupported fake codex command")
                state_path.parent.mkdir(parents=True, exist_ok=True)
                state_path.write_text(json.dumps(state))
                print(json.dumps({"ok": True}))
                """
            ).lstrip())
            (command_dir / "codex").chmod(0o755)
            fake_state = home / ".codex/fake-state.json"
            preserved = (old_runtime, old_bin)
            def snapshot_preserved():
                return {
                    path.relative_to(home).as_posix(): path.read_bytes()
                    for root_path in preserved
                    for path in root_path.rglob("*")
                    if path.is_file()
                }

            test_env = {
                **os.environ, "HOME": str(home),
                "PATH": str(command_dir) + os.pathsep + os.environ["PATH"],
            }
            clean = subprocess.run(["git", "status", "--porcelain"], cwd=source, text=True, capture_output=True, check=True)
            self.assertEqual("", clean.stdout, clean.stderr)

            def sync_validate(**extra_env):
                return subprocess.run(
                    ["bash", "scripts/sync-live.sh", "--validate"],
                    cwd=source, env={**test_env, **extra_env}, text=True, capture_output=True, check=False,
                )

            fake_state.parent.mkdir(parents=True)
            fake_state.write_text(json.dumps({"marketplaces": {"cse": str(root / "elsewhere")}, "installed": []}))
            before = snapshot_preserved()
            refused = sync_validate()
            self.assertNotEqual(0, refused.returncode)
            self.assertIn("remove it with `codex plugin marketplace remove cse`", refused.stderr)
            self.assertEqual(before, snapshot_preserved())

            fake_state.write_text(json.dumps({"marketplaces": {}, "installed": [{"pluginId": "cse@personal", "installed": True}]}))
            duplicate = sync_validate()
            self.assertNotEqual(0, duplicate.returncode)
            self.assertIn("cse@personal", duplicate.stderr)
            self.assertEqual(before, snapshot_preserved())

            empty_state = {"marketplaces": {}, "installed": []}
            fake_state.write_text(json.dumps(empty_state))
            readme = source / "README.md"
            committed_readme = readme.read_text()
            readme.write_text(committed_readme + "uncommitted\n")
            dirty = sync_validate()
            self.assertNotEqual(0, dirty.returncode)
            self.assertIn("Refusing to deploy an uncommitted source tree.", dirty.stderr)
            self.assertEqual(before, snapshot_preserved())
            self.assertEqual(empty_state, json.loads(fake_state.read_text()))
            readme.write_text(committed_readme)
            # Untracked files beside the plugin are not deployed and must not block it.
            (runtime / "untracked-note.txt").write_text("local only\n")
            for failure in ("bin-backup:before:zotero-companion", "late:after-install"):
                failed = sync_validate(CSE_FAIL_AT=failure)
                self.assertNotEqual(0, failed.returncode)
                self.assertIn(f"Injected failure at {failure}", failed.stderr)
                self.assertEqual(before, snapshot_preserved())
                self.assertEqual(empty_state, json.loads(fake_state.read_text()), failure)
                self.assertFalse((home / ".codex/plugins/cache/cse/cse/local").exists())

            installed = sync_validate()
            self.assertEqual(0, installed.returncode, installed.stderr)
            identity = json.loads(next(line for line in installed.stdout.splitlines() if '"pluginCommit"' in line))
            self.assertEqual(40, len(identity["pluginCommit"]))
            self.assertEqual(identity["pluginCommit"], identity["zoteroCommit"])
            self.assertEqual(64, len(identity["payloadSha256"]))
            state = json.loads(fake_state.read_text())
            self.assertEqual({"cse": str(source.resolve())}, state["marketplaces"])
            self.assertEqual(["cse@cse"], [item["pluginId"] for item in state["installed"]])
            self.assertTrue((home / ".codex/plugins/cache/cse/cse/local/skills").is_dir())
            self.assertEqual('{"module_revision": 20}\n', agent_build.read_text())
            self.assertFalse((home / ".codex/plugins/cse").exists())
            self.assertFalse((home / ".agents/plugins/marketplace.json").exists())
            for command in ("cse-zotero", "zotero-companion"):
                entry = home / ".local/bin" / command
                self.assertTrue(entry.is_symlink())
                self.assertTrue(entry.resolve().is_file())

    def test_sync_check_exercises_data_handoff_in_the_installed_wheel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            source = repository / "cse-plugin"
            shutil.copytree(ROOT, source, ignore=PLUGIN_IGNORE)
            zotero = subprocess.run(["git", "-C", str(ROOT.parent), "archive", "HEAD", "cse-zotero"], capture_output=True, check=True)
            subprocess.run(["tar", "-x", "-C", str(repository)], input=zotero.stdout, check=True)
            validate = source / "scripts/validate.sh"
            validate.write_text("#!/usr/bin/env bash\nexit 0\n")
            validate.chmod(0o755)
            self.git_fixture(repository)
            home = root / "home"
            home.mkdir()
            uv_cache = os.environ.get("UV_CACHE_DIR") or subprocess.run(
                ["uv", "cache", "dir"], text=True, capture_output=True, check=True,
            ).stdout.strip()
            result = subprocess.run(
                ["bash", "scripts/sync-live.sh", "--check"],
                cwd=source,
                env={**os.environ, "HOME": str(home), "UV_CACHE_DIR": uv_cache},
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            identity = json.loads(next(line for line in result.stdout.splitlines() if "pluginCommit" in line))
            self.assertEqual(identity["pluginCommit"], identity["zoteroCommit"])
            self.assertIn("data-register/data-select/query lineage checks passed", identity["runtime"])
            self.assertFalse((home / ".codex/plugins/cse").exists())
            self.assertFalse((home / ".local/share/cse/zotero").exists())


if __name__ == "__main__":
    unittest.main()
