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


class InstallationBehaviorTests(unittest.TestCase):
    def git_fixture(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"], cwd=root, check=True)

    def test_sync_migrates_old_packages_and_rolls_back_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", ".runs", "__pycache__", ".pytest_cache"))
            with (source / ".gitignore").open("a") as ignore:
                ignore.write("\n.idea/\n")
            validate = source / "scripts/validate.sh"
            validate.write_text("#!/usr/bin/env bash\nexit 0\n")
            validate.chmod(0o755)
            self.git_fixture(source)
            runtime = root / "zotero"
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
            self.git_fixture(runtime)
            home = root / "home"
            deploy = home / ".codex/plugins"
            deploy.mkdir(parents=True)
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source, text=True, capture_output=True, check=True).stdout.strip()
            subprocess.run(
                ["python3", "scripts/package_inventory.py", "stage", "cse", str(deploy / "cse"), "--commit", commit, "--home", str(home)],
                cwd=source, check=True, capture_output=True, text=True,
            )
            for name in ("cse-sources", "cse-visualize"):
                (deploy / name / ".codex-plugin").mkdir(parents=True)
                (deploy / name / ".codex-plugin/plugin.json").write_text(json.dumps({"name": name}))
            old_runtime = home / ".local/share/cse/zotero"
            old_runtime.mkdir(parents=True)
            (old_runtime / "previous.txt").write_text("previous runtime\n")
            old_bin = home / ".local/bin"
            old_bin.mkdir(parents=True)
            for command in ("cse-zotero", "zotero-companion"):
                (old_bin / command).write_text(f"previous {command}\n")
            unrelated = home / ".agents/plugins/marketplace.json"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text(json.dumps({"name": "personal", "plugins": [
                {"name": "other"},
                {"name": "cse", "source": {"source": "local", "path": "./.codex/plugins/cse"}},
                {"name": "cse-sources", "source": {"source": "local", "path": "./.codex/plugins/cse-sources"}},
                {"name": "cse-visualize", "source": {"source": "local", "path": "./.codex/plugins/cse-visualize"}},
            ]}))
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
                state_path = home / ".codex/fake-plugin-state.json"
                marketplace_state_path = home / ".codex/fake-marketplaces.json"
                state_path.parent.mkdir(parents=True, exist_ok=True)
                state = json.loads(state_path.read_text()) if state_path.exists() else {"installed": []}
                marketplace_state = (
                    json.loads(marketplace_state_path.read_text())
                    if marketplace_state_path.exists()
                    else {"marketplaces": []}
                )
                args = sys.argv[1:]
                manifest_path = home / ".agents/plugins/marketplace.json"

                def save_state():
                    state_path.write_text(json.dumps(state))

                def save_marketplaces():
                    marketplace_state_path.write_text(json.dumps(marketplace_state))

                if args[:3] == ["plugin", "marketplace", "list"]:
                    entries = list(marketplace_state.get("marketplaces", []))
                    if manifest_path.is_file() and not any(item.get("name") == "personal" for item in entries):
                        entries.append({"name": "personal", "root": str(home)})
                    print(json.dumps({"marketplaces": entries}))
                    raise SystemExit

                if args[:3] == ["plugin", "marketplace", "add"]:
                    source = Path(args[3]).resolve()
                    if source != home.resolve():
                        raise SystemExit("fake marketplace only accepts the task home")
                    entries = list(marketplace_state.get("marketplaces", []))
                    already_added = any(
                        item.get("name") == "personal" and item.get("marketplaceSource")
                        for item in entries
                    )
                    if not already_added:
                        entries = [item for item in entries if item.get("name") != "personal"]
                        entries.append({
                            "name": "personal",
                            "root": str(home),
                            "marketplaceSource": {"sourceType": "local", "source": str(home)},
                        })
                        marketplace_state["marketplaces"] = entries
                        save_marketplaces()
                    print(json.dumps({
                        "marketplaceName": "personal",
                        "installedRoot": str(home),
                        "alreadyAdded": already_added,
                    }))
                    raise SystemExit

                if args[:3] == ["plugin", "marketplace", "remove"]:
                    name = args[3]
                    marketplace_state["marketplaces"] = [
                        item for item in marketplace_state.get("marketplaces", [])
                        if item.get("name") != name
                    ]
                    save_marketplaces()
                    print(json.dumps({"ok": True}))
                    raise SystemExit

                if args[:2] == ["plugin", "list"]:
                    print(json.dumps(state))
                    raise SystemExit

                selector = next((token for token in args[2:] if not token.startswith("-")), "")
                name = selector.split("@", 1)[0]
                durable = home / ".codex/plugins" / name
                cache = home / ".codex/plugins/cache/personal" / name / "local"
                if args[:2] == ["plugin", "remove"]:
                    if cache.exists():
                        shutil.rmtree(cache)
                    state["installed"] = [
                        item for item in state["installed"]
                        if item.get("pluginId") != name + "@personal"
                    ]
                elif args[:2] == ["plugin", "add"]:
                    marketplace = json.loads(manifest_path.read_text())
                    item = next(item for item in marketplace["plugins"] if item["name"] == name)
                    raw = Path(item["source"]["path"])
                    origin = (home / raw).resolve() if not raw.is_absolute() else raw
                    if not origin.is_dir():
                        raise SystemExit(f"missing durable source: {origin}")
                    if cache.exists():
                        shutil.rmtree(cache)
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(origin, cache)
                    state["installed"] = [
                        item for item in state["installed"]
                        if item.get("pluginId") != name + "@personal"
                    ]
                    state["installed"].append({
                        "pluginId": name + "@personal",
                        "installed": True,
                        "enabled": True,
                        "source": {"path": str(durable)},
                    })
                else:
                    raise SystemExit("unsupported fake codex command")
                save_state()
                print(json.dumps({"ok": True}))
                """
            ).lstrip())
            (command_dir / "codex").chmod(0o755)
            (command_dir / "git").write_text(textwrap.dedent(
                """
                #!/usr/bin/env python3
                import os
                from pathlib import Path
                import sys

                args = sys.argv[1:]
                real_git = os.environ["CSE_REAL_GIT"]
                runtime = Path(os.environ["CSE_TEST_ZOTERO_ROOT"]).resolve()
                expected = "e82ebbee4b6896b0f513727cdbac2a18e31bbf24"
                if args[:2] == ["-C", str(runtime)]:
                    if args[2:] == ["rev-parse", "HEAD"]:
                        print(expected)
                        raise SystemExit
                    if args[2:] == ["archive", expected]:
                        os.execv(real_git, [real_git, "-C", str(runtime), "archive", "HEAD"])
                os.execv(real_git, [real_git, *args])
                """
            ).lstrip())
            (command_dir / "git").chmod(0o755)
            state = {"installed": [{"pluginId": name + "@personal", "installed": True, "enabled": True, "source": {"path": str(deploy / name)}} for name in ("cse", "cse-sources", "cse-visualize")]}
            (home / ".codex/fake-plugin-state.json").parent.mkdir(parents=True, exist_ok=True)
            (home / ".codex/fake-plugin-state.json").write_text(json.dumps(state))
            (home / ".codex/fake-marketplaces.json").write_text(json.dumps({"marketplaces": []}))
            previous_state = json.loads((home / ".codex/fake-plugin-state.json").read_text())
            previous_marketplaces = json.loads((home / ".codex/fake-marketplaces.json").read_text())
            preserved = (deploy / "cse", deploy / "cse-sources", deploy / "cse-visualize", old_runtime, old_bin, unrelated)
            def snapshot_preserved():
                return {
                    path.relative_to(home).as_posix(): path.read_bytes()
                    for root_path in preserved
                    for path in ((root_path,) if root_path.is_file() else root_path.rglob("*"))
                    if path.is_file()
                }

            test_env = {
                **os.environ, "HOME": str(home),
                "PATH": str(command_dir) + os.pathsep + os.environ["PATH"],
                "CSE_REAL_GIT": shutil.which("git"),
                "CSE_TEST_ZOTERO_ROOT": str(runtime.resolve()),
            }
            clean = subprocess.run(["git", "status", "--porcelain"], cwd=source, text=True, capture_output=True, check=True)
            self.assertEqual("", clean.stdout, clean.stderr)

            untrusted = root / "untrusted-zotero"
            shutil.copytree(runtime, untrusted, ignore=shutil.ignore_patterns(".git"))
            (untrusted / ".cse-source-commit").write_text("e82ebbee4b6896b0f513727cdbac2a18e31bbf24\n")
            rejected = subprocess.run(
                ["bash", "scripts/sync-live.sh", "--check", "--zotero-source", str(untrusted)],
                cwd=source, env=test_env, text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(0, rejected.returncode)
            self.assertIn("must be a Git checkout", rejected.stderr)

            wrong_manifest = deploy / "cse-visualize/.codex-plugin/plugin.json"
            wrong_manifest.write_text(json.dumps({"name": "not-cse"}))
            wrong_sentinel = deploy / "cse-visualize/user-sentinel"
            wrong_sentinel.write_text("preserve me\n")
            wrong_before = snapshot_preserved()
            refused = subprocess.run(
                ["bash", "scripts/sync-live.sh", "--validate", "--zotero-source", str(runtime)],
                cwd=source, env=test_env, text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(0, refused.returncode)
            self.assertIn("Refusing unexpected directory", refused.stderr)
            self.assertEqual(wrong_before, snapshot_preserved())
            wrong_manifest.write_text(json.dumps({"name": "cse-visualize"}))
            wrong_sentinel.unlink()

            before = snapshot_preserved()
            for failure in ("bin-backup:before:zotero-companion", "late:after-runtime"):
                failed = subprocess.run(
                    ["bash", "scripts/sync-live.sh", "--validate", "--zotero-source", str(runtime)],
                    cwd=source, env={**test_env, "CSE_FAIL_AT": failure},
                    text=True, capture_output=True, check=False,
                )
                self.assertNotEqual(0, failed.returncode)
                self.assertEqual(before, snapshot_preserved())
                self.assertEqual(previous_state, json.loads((home / ".codex/fake-plugin-state.json").read_text()))
                self.assertEqual(previous_marketplaces, json.loads((home / ".codex/fake-marketplaces.json").read_text()))
            clean_after_failure = subprocess.run(
                ["git", "status", "--porcelain"], cwd=source,
                text=True, capture_output=True, check=False,
            )
            self.assertEqual("", clean_after_failure.stdout, clean_after_failure.stderr)

            installed = subprocess.run(
                ["bash", "scripts/sync-live.sh", "--validate", "--zotero-source", str(runtime)], cwd=source,
                env=test_env, text=True, capture_output=True, check=False,
            )
            status = subprocess.run(["git", "status", "--porcelain"], cwd=source, env={**os.environ, "HOME": str(home)}, text=True, capture_output=True, check=True).stdout
            self.assertEqual(0, installed.returncode, f"{installed.stderr}\nstatus={status}")
            identity = json.loads(next(line for line in installed.stdout.splitlines() if '"pluginCommit"' in line))
            self.assertEqual("e82ebbee4b6896b0f513727cdbac2a18e31bbf24", identity["zoteroCommit"])
            self.assertEqual(40, len(identity["pluginCommit"]))
            self.assertEqual(64, len(identity["payloadSha256"]))
            self.assertTrue((deploy / "cse").is_dir())
            self.assertFalse((deploy / "cse-sources").exists())
            self.assertFalse((deploy / "cse-visualize").exists())
            self.assertTrue((home / ".codex/plugins/cache/personal/cse/local").is_dir())
            for command in ("cse-zotero", "zotero-companion"):
                entry = home / ".local/bin" / command
                self.assertTrue(entry.is_symlink())
                self.assertTrue(entry.resolve().is_file())
            self.assertEqual("./.codex/plugins/cse", json.loads(unrelated.read_text())["plugins"][1]["source"]["path"])
            self.assertFalse(any(
                path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
                for path in (home / ".codex/plugins/cse").rglob("*")
            ))
            names = [item["name"] for item in json.loads(unrelated.read_text())["plugins"]]
            self.assertEqual(["other", "cse"], names)


if __name__ == "__main__":
    unittest.main()
