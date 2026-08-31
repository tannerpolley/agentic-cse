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
                "Repository " + "Profile: scientific-computing\n"
            )
            self.assertEqual(invoke().stdout, "")

            context = repository / "docs/scientific/CONTEXT.md"
            context.parent.mkdir(parents=True)
            context.write_text("# Scientific context\n")
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
            home = root / "home"
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                capture_output=True, check=True,
            ).stdout.strip()
            names = ("cse", "cse-sources", "cse-visualize")
            versions = {"cse": "2.0.0", "cse-sources": "1.0.0", "cse-visualize": "1.0.0"}
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
                self.assertTrue(json.loads(result.stdout)["enabled"])

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
                ({"installed": [record("cse"), record("cse-sources"), record("cse-visualize", version="9.0.0")]}, "version does not match"),
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
            self.assertIn("stale, altered, or incompatible", rejected.stderr)
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
                "---\nformat: pdf\n---\n\n"
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
                ["bash", "render.sh", "document.qmd"],
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

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(identified_removed)
        self.assertEqual(preserved_result.returncode, 0, preserved_result.stderr)
        self.assertEqual(preserved, "user directory\n")
        deployed = home / ".codex/plugins/cse"
        self.assertFalse((deployed / "examples").exists())
        self.assertFalse((deployed / "cse-pi-harness").exists())
        self.assertFalse((deployed / "docs").exists())
        self.assertFalse((deployed / "evaluation").exists())
        self.assertFalse((deployed / ".runs").exists())
        self.assertFalse((deployed / "scripts/cooling_fit_benchmark.py").exists())

    def test_every_family_failure_checkpoint_is_atomic_for_first_install_and_upgrade(self):
        packages = ("cse", "cse-sources", "cse-visualize")
        checkpoints = tuple(
            f"{phase}:{side}:{name}"
            for phase in ("validate", "stage", "deploy", "register")
            for side in ("before", "after")
            for name in packages
        )

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
                    "HOME": str(home), "CSE_PLUGIN_VALIDATOR": str(validator),
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
            prior_state = state(prior)

            for checkpoint in checkpoints:
                with self.subTest(mode="first", checkpoint=checkpoint):
                    home = root / "first" / checkpoint.replace(":", "-")
                    legacy = home / ".codex/plugins/scientific-codex/.codex-plugin"
                    legacy.mkdir(parents=True)
                    (legacy / "plugin.json").write_text(json.dumps({"name": "scientific-codex"}))
                    marketplace = home / ".agents/plugins/marketplace.json"
                    marketplace.parent.mkdir(parents=True)
                    marketplace.write_text(json.dumps({"name": "personal", "plugins": [{"name": "other"}, {"name": "scientific-codex"}]}))
                    before = state(home)
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
