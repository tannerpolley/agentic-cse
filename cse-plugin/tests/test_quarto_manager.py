from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import call, patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugin/assets/visualize/project/quarto/manuscript.py"
SPEC = importlib.util.spec_from_file_location("cse_manuscript", SCRIPT)
assert SPEC and SPEC.loader
MANUSCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MANUSCRIPT)


class QuartoManagerTests(unittest.TestCase):
    def test_only_the_recognized_presentation_hook_is_allowed(self):
        path = Path("_quarto-presentation.yml")
        allowed = {"project": {"pre-render": MANUSCRIPT.PRESENTATION_PRE_RENDER}}
        MANUSCRIPT.check_owners(allowed, path, allow_presentation_hook=True)

        for value in (
            {"project": {"pre-render": "snakemake --cores 1 calculate"}},
            {"project": {"pre-render": [MANUSCRIPT.PRESENTATION_PRE_RENDER, "other"]}},
            {"project": {"post-render": MANUSCRIPT.PRESENTATION_PRE_RENDER}},
            {"project": {"pre-render": MANUSCRIPT.PRESENTATION_PRE_RENDER}},
        ):
            with self.subTest(value=value):
                with self.assertRaises(MANUSCRIPT.ManuscriptError):
                    MANUSCRIPT.check_owners(value, path, allow_presentation_hook=value is allowed)

    def test_earlier_manuscript_root_is_refused_with_rebuild_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_quarto.yml").write_text('{"project": {"type": "manuscript", "output-dir": "_site"}}\n')
            with self.assertRaisesRegex(MANUSCRIPT.ManuscriptError, "rerunning init"):
                MANUSCRIPT.check_boundary(root)

    def test_init_on_a_managed_root_replaces_only_plugin_tooling(self):
        with tempfile.TemporaryDirectory() as directory:
            initial = Path(directory) / "initial"
            initial.mkdir()
            (initial / "index.qmd").write_text("# Synthesis\n")
            with (patch.object(MANUSCRIPT, "home_section", return_value={}),
                  patch.object(MANUSCRIPT, "validate_root")):
                MANUSCRIPT.init(initial, initial / "index.qmd", "c" * 40, "d" * 64)
            self.assertEqual((SCRIPT.parent / "preview.service").read_bytes(),
                             (initial / "preview.service").read_bytes())

            root = Path(directory) / "analyses"
            root.mkdir()
            owned = {"_quarto.yml": json.dumps(MANUSCRIPT.SITE_CONFIG), "_cse-manuscript.json": '{"project": 1}\n',
                     "site.css": "body { color: teal; }\n", "index.qmd": "# Synthesis\n",
                     ".gitignore": "\n".join((*MANUSCRIPT.REQUIRED_IGNORES, "/scratch/")) + "\n"}
            for name in MANUSCRIPT.TOOLING_FILES:
                (root / name).write_text("older plugin copy\n")
            for name, text in owned.items():
                (root / name).write_text(text)
            with (patch.object(MANUSCRIPT, "home_section", return_value={}),
                  patch.object(MANUSCRIPT, "validate_root")):
                _, replaced = MANUSCRIPT.init(root, root / "index.qmd", "c" * 40, "d" * 64)

            self.assertEqual(sorted(MANUSCRIPT.TOOLING_FILES), sorted(replaced))
            for name in ("_quarto-presentation.yml", "render.sh", "manuscript.py", "preview.service"):
                self.assertEqual((SCRIPT.parent / name).read_bytes(), (root / name).read_bytes())
            self.assertEqual("c" * 40, json.loads((root / ".cse-quarto-source.json").read_text())["sourceCommit"])
            self.assertEqual(owned, {name: (root / name).read_text() for name in owned})

    def test_refresh_renders_notebook_then_root_with_presentation_cache_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notebook = root / "case" / "notebook.qmd"
            notebook.parent.mkdir()
            notebook.write_text("notebook\n")
            state = {"project": {"render": ["index.qmd", "case/notebook.qmd"]}}
            completed = subprocess.CompletedProcess([], 0)
            events = []

            def prepared(value):
                events.append("prepare")
                return 0

            def rendered(*args, **kwargs):
                events.append("render")
                return completed

            with (
                patch.object(MANUSCRIPT, "sync", return_value=state),
                patch.object(MANUSCRIPT, "notebook_argument", return_value="case/notebook.qmd"),
                patch.object(MANUSCRIPT, "prepare", side_effect=prepared),
                patch.object(MANUSCRIPT.subprocess, "run", side_effect=rendered) as run,
            ):
                self.assertEqual(0, MANUSCRIPT.refresh(root, notebook))

            self.assertEqual(["prepare", "render", "render"], events)
            self.assertEqual(
                [
                    ["quarto", "render", "case/notebook.qmd", "--to", "html", "--profile", "presentation", "--cache-refresh"],
                    ["quarto", "render", "index.qmd", "--to", "html", "--profile", "presentation", "--cache-refresh"],
                ],
                [call.args[0] for call in run.call_args_list],
            )

    def test_prepare_invokes_only_the_presentation_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis = root / "case"
            analysis.mkdir()
            dry_run = subprocess.CompletedProcess(
                [], 0,
                stdout=(
                    "Building DAG of jobs...\n"
                    '{"nodes": [{"id": 0, "value": {"jobid": 0, "label": "present", "rule": "present"}}], "edges": []}\n'
                ),
                stderr="",
            )
            completed = subprocess.CompletedProcess([], 0)
            with (
                patch.object(MANUSCRIPT, "presentation_workflows", return_value=[analysis]),
                patch.object(MANUSCRIPT.subprocess, "run", side_effect=[dry_run, completed]) as run,
            ):
                self.assertEqual(0, MANUSCRIPT.prepare(root))

            self.assertEqual(
                [
                    ["snakemake", "--cores", "1", "--dry-run", "--quiet", "--d3dag", "present"],
                    ["snakemake", "--cores", "1", "present"],
                ],
                [item.args[0] for item in run.call_args_list],
            )
            run.assert_any_call(
                ["snakemake", "--cores", "1", "present"], cwd=analysis, check=False
            )

    def test_preview_render_skips_an_unchanged_workflow_until_a_file_changes(self):
        # A present step that rewrites its figures must not re-trigger Quarto's render forever.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis = root / "case"
            analysis.mkdir()
            (analysis / "retained.csv").write_text("1\n")
            dry_run = subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({"nodes": [{"value": {"rule": "present"}}]}), stderr=""
            )
            completed = subprocess.CompletedProcess([], 0)
            with (
                patch.dict(os.environ, {MANUSCRIPT.PREVIEW_STAMPS_ENV: "1"}),
                patch.object(MANUSCRIPT, "presentation_workflows", return_value=[analysis]),
                patch.object(MANUSCRIPT.subprocess, "run", side_effect=[dry_run, completed, dry_run, completed]) as run,
            ):
                self.assertEqual(0, MANUSCRIPT.prepare(root))
                self.assertEqual(0, MANUSCRIPT.prepare(root))
                self.assertEqual(2, run.call_count)
                (analysis / "retained.csv").write_text("2\n")
                self.assertEqual(0, MANUSCRIPT.prepare(root))
                self.assertEqual(4, run.call_count)

    def test_prepare_limits_incremental_render_to_the_requested_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            dry_run = subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({"nodes": [{"value": {"rule": "present"}}]}), stderr=""
            )
            completed = subprocess.CompletedProcess([], 0)
            with (
                patch.dict(os.environ, {"QUARTO_PROJECT_INPUT_FILES": "first/notebook.qmd"}),
                patch.object(MANUSCRIPT, "presentation_workflows", return_value=[first, second]),
                patch.object(MANUSCRIPT.subprocess, "run", side_effect=[dry_run, completed]) as run,
            ):
                self.assertEqual(0, MANUSCRIPT.prepare(root))

            self.assertEqual(2, run.call_count)
            run.assert_any_call(
                ["snakemake", "--cores", "1", "present"], cwd=first, check=False
            )

    def test_prepare_stops_after_a_failed_presentation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            dry_run = subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({"nodes": [{"value": {"rule": "present"}}]}), stderr=""
            )
            failed = subprocess.CompletedProcess([], 7)
            with (
                patch.object(MANUSCRIPT, "presentation_workflows", return_value=[first, second]),
                patch.object(MANUSCRIPT.subprocess, "run", side_effect=[dry_run, failed]) as run,
            ):
                self.assertEqual(7, MANUSCRIPT.prepare(root))

            self.assertEqual(2, run.call_count)
            run.assert_any_call(
                ["snakemake", "--cores", "1", "present"], cwd=first, check=False
            )

    def test_prepare_refuses_a_calculation_job_in_the_dry_run_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis = root / "case"
            analysis.mkdir()
            dry_run = subprocess.CompletedProcess(
                [], 0,
                stdout=json.dumps({"nodes": [
                    {"value": {"rule": "present"}},
                    {"value": {"rule": "calculate"}},
                ]}),
                stderr="",
            )
            output = io.StringIO()
            with (
                patch.object(MANUSCRIPT, "presentation_workflows", return_value=[analysis]),
                patch.object(MANUSCRIPT.subprocess, "run", return_value=dry_run) as run,
                contextlib.redirect_stderr(output),
            ):
                self.assertNotEqual(0, MANUSCRIPT.prepare(root))

            run.assert_called_once()
            self.assertIn("calculate", output.getvalue())
            self.assertIn("extra jobs refused", output.getvalue())

    def test_preview_bridge_prepares_before_rendering_and_keeps_stale_sources_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with (
                patch.object(MANUSCRIPT, "prepare", return_value=7) as prepare,
                patch.object(MANUSCRIPT, "request_renders") as render,
                contextlib.redirect_stderr(output),
            ):
                self.assertEqual(7, MANUSCRIPT.prepare_and_render(root, {}, {root / "case" / "results.json"}, "127.0.0.1", 8000))

            prepare.assert_called_once_with(root)
            render.assert_not_called()
            self.assertIn("retained pages remain stale", output.getvalue())

    def test_changed_retained_file_notifies_its_notebook_and_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = {"website": {"sidebar": {"contents": [{"section": "Home", "contents": [{"text": "Overview", "href": "index.qmd"}]}, {"section": "Case", "contents": [{"text": "Results", "href": "case/notebook.qmd#results"}]}]}}}
            changed = {root / "case" / "results" / "fit_summary.json"}
            self.assertEqual(
                {root / "index.qmd", root / "case" / "notebook.qmd"},
                MANUSCRIPT.presentation_targets(root, state, changed),
            )

    def test_generated_include_is_a_watch_trigger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "case" / "results" / "cooling_fit_include.qmd"
            self.assertTrue(MANUSCRIPT.is_watchable(generated, root))

    def test_scan_prunes_retained_trees_but_tracks_exact_nested_includes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "case/results").mkdir(parents=True)
            (root / "data/large").mkdir(parents=True)
            (root / "case/notebook.qmd").write_text("{{< include results/table.md >}}\n")
            fragment = root / "case/results/table.md"
            fragment.write_text("{{< include values.qmd >}}\n")
            values = root / "case/results/values.qmd"
            values.write_text("1\n")
            (root / "case/results/unused.csv").write_text("1\n")
            (root / "data/large/input.csv").write_text("1\n")
            visited = []
            real_walk = os.walk

            def walk(*args, **kwargs):
                for entry in real_walk(*args, **kwargs):
                    visited.append(Path(entry[0]))
                    yield entry

            with patch.object(MANUSCRIPT.os, "walk", side_effect=walk):
                before = MANUSCRIPT.watch_snapshot(root)
            self.assertEqual({root / "case/notebook.qmd", fragment, values}, set(before))
            self.assertFalse(any({"data", "results"} & set(path.relative_to(root).parts) for path in visited))
            values.write_text("updated\n")
            self.assertEqual({values}, MANUSCRIPT.changed_paths(before, MANUSCRIPT.watch_snapshot(root)))
            fragment.unlink()
            self.assertIn(fragment, MANUSCRIPT.changed_paths(before, MANUSCRIPT.watch_snapshot(root)))

    def test_generated_and_cache_paths_are_not_watch_triggers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ignored = (
                ".snakemake/log.txt", ".cache/state", "tmp/file", "temp/file",
                "index_files/image.png", "_site/page.html",
                "_freeze/page.json", "support/asset.bin", "site_libs/bootstrap/theme.css",
                "case/notebook.html",
            )
            for relative in ignored:
                with self.subTest(relative=relative):
                    self.assertFalse(MANUSCRIPT.is_watchable(root / relative, root))
            self.assertTrue(MANUSCRIPT.is_watchable(root / "case" / "notebook.qmd", root))

    def test_worktree_preview_allocates_a_port_and_stop_cleans_up_quarto(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            repository = parent / "repo"
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(["git", "-C", str(repository), "-c", "user.name=Test", "-c", "user.email=test@example.com",
                            "commit", "-qm", "initial", "--allow-empty"], check=True)
            worktree = parent / "worktree"
            subprocess.run(["git", "-C", str(repository), "worktree", "add", "-qb", "task", str(worktree)], check=True)
            root = worktree / "analyses"
            root.mkdir()
            units = parent / "config/systemd/user"
            units.mkdir(parents=True)
            candidate = MANUSCRIPT.preview_port(worktree, None)
            units.joinpath("cse-preview-other.service").write_text(f"ExecStart=python preview --port {candidate}\n")
            bin_dir = parent / "bin"
            bin_dir.mkdir()
            pid_file = parent / "quarto.pid"
            fake_quarto = bin_dir / "quarto"
            fake_quarto.write_text(
                "#!/usr/bin/env python3\n"
                "import os\n"
                "from pathlib import Path\n"
                "import time\n"
                "Path(os.environ['FAKE_QUARTO_PID']).write_text(str(os.getpid()))\n"
                "while True:\n"
                "    time.sleep(1)\n"
            )
            fake_quarto.chmod(0o755)
            runner = parent / "runner.py"
            runner.write_text(
                "import importlib.util\n"
                "from pathlib import Path\n"
                "import sys\n"
                f"spec = importlib.util.spec_from_file_location('manuscript', {str(SCRIPT)!r})\n"
                "module = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(module)\n"
                "module.validate_root = module.sync = lambda root: {}\n"
                "module.presentation_workflows = lambda root: []\n"
                "raise SystemExit(module.preview(Path(sys.argv[1]), '127.0.0.1', None))\n"
            )
            environment = {
                **os.environ,
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                "FAKE_QUARTO_PID": str(pid_file),
                "XDG_CONFIG_HOME": str(parent / "config"),
            }
            process = subprocess.Popen(
                [sys.executable, str(runner), str(root)],
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                record = root / ".quarto/cse-preview.json"
                deadline = time.monotonic() + 5
                while (not pid_file.exists() or not record.exists()) and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(pid_file.exists() and record.exists(), process.stderr.read() if process.poll() is not None else "")
                fake_pid = int(pid_file.read_text())
                port = json.loads(record.read_text())["port"]
                self.assertTrue(8800 <= port < 9800)
                self.assertNotEqual(candidate, port)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    MANUSCRIPT.status(root)
                self.assertIn(f"state: running\nport: {port}\nurl: http://127.0.0.1:{port}/", output.getvalue())
                with self.assertRaisesRegex(MANUSCRIPT.ManuscriptError, "main-checkout service is always on"):
                    MANUSCRIPT.stop(repository)
                with contextlib.redirect_stdout(io.StringIO()):
                    MANUSCRIPT.stop(root)
                stdout, stderr = process.communicate(timeout=5)
                self.assertEqual(130, process.returncode, (stdout, stderr))
                self.assertFalse(record.exists())
                with self.assertRaises(ProcessLookupError):
                    os.kill(fake_pid, 0)
                record.write_text(json.dumps({"pid": os.getpid(), "identity": "stale", "port": port, "host": "127.0.0.1"}))
                with patch.object(MANUSCRIPT.os, "kill") as kill, contextlib.redirect_stdout(io.StringIO()):
                    MANUSCRIPT.stop(root)
                kill.assert_not_called()
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    process.communicate(timeout=5)

    def test_only_results_includes_are_adopted_as_source_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "case" / "results").mkdir(parents=True)
            source = root / "case" / "notebook.qmd"
            fragment = root / "case" / "results" / "table.qmd"
            source.write_text("{{< include results/table.qmd >}}\n")
            fragment.write_text("| value |\n| --- |\n| 1 |\n")
            files = {"case/notebook.qmd": source.read_bytes()}
            included = MANUSCRIPT.included_files(root, files, ["case/notebook.qmd"])
            self.assertEqual({"case/results/table.qmd"}, set(included))

            source.write_text("{{< include notes/table.qmd >}}\n")
            with self.assertRaises(MANUSCRIPT.ManuscriptError):
                MANUSCRIPT.included_files(root, {"case/notebook.qmd": source.read_bytes()}, ["case/notebook.qmd"])

    @contextlib.contextmanager
    def preview_service(self):
        real_run = subprocess.run
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            repository = base / "repo"
            (repository / "analyses").mkdir(parents=True)
            real_run(["git", "init", "-q", str(repository)], check=True)
            python = repository / ".venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("")
            python.chmod(0o755)
            state = {"base": base, "repository": repository, "python": python, "units": base / "config/systemd/user",
                     "systemctl": [], "busy": set(), "missing": False}

            def run(command, *args, **kwargs):
                if command[0] == "systemctl":
                    state["systemctl"].append(command[2])
                    return subprocess.CompletedProcess(command, 0, stdout="active\n")
                if command[0] == str(python):
                    return subprocess.CompletedProcess(command, int(state["missing"]),
                                                       stderr="ModuleNotFoundError: No module named 'jupyter_cache'" if state["missing"] else "")
                return real_run(command, *args, **kwargs)

            def install(root=repository / "analyses", port=None, interpreter=None):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    status = MANUSCRIPT.service(root, port, False, interpreter)
                return status, output.getvalue()

            state["install"] = install
            with (
                patch.dict(os.environ, {"XDG_CONFIG_HOME": str(base / "config")}),
                patch.object(MANUSCRIPT, "sync"),
                patch.object(MANUSCRIPT.shutil, "which", return_value="/opt/quarto/bin/quarto"),
                patch.object(MANUSCRIPT.subprocess, "run", side_effect=run),
                patch.object(MANUSCRIPT, "port_free", side_effect=lambda port: port not in state["busy"]),
                patch.object(MANUSCRIPT, "answering", return_value=True),
            ):
                yield state

    def test_preview_service_keeps_its_port_skips_claimed_ports_and_refuses_foreign_units(self):
        with self.preview_service() as state:
            repository, install, systemctl = state["repository"], state["install"], state["systemctl"]
            bound = MANUSCRIPT.preview_port(repository, None)
            state["busy"].add(bound)
            self.assertEqual(0, install()[0])
            unit = next(state["units"].glob("cse-preview-repo-*.service"))
            text = unit.read_text()
            port = MANUSCRIPT.service_port(unit)
            self.assertNotEqual(bound, port)
            self.assertIn(f"\nWorkingDirectory={repository}\n", text)
            self.assertIn(f"\nExecStart={state['python']} analyses/manuscript.py preview analyses "
                          f"--host 127.0.0.1 --port {port}\n", text)
            self.assertIn(f"\nEnvironment=PATH={state['python'].parent}:/opt/quarto/bin:", text)
            self.assertIn("\nNice=10\nCPUWeight=10\n", text)
            self.assertIn("\nRestart=on-failure\n", text)
            self.assertEqual(["show-environment", "daemon-reload", "enable", "restart"], systemctl)

            systemctl.clear()
            state["busy"].add(port)
            self.assertEqual(0, install()[0])
            self.assertEqual((text, ["show-environment", "daemon-reload", "enable", "restart"]), (unit.read_text(), systemctl))

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                MANUSCRIPT.status(repository / "analyses")
            self.assertIn(f"unit: {unit.name}\nstate: active\nport: {port}\nurl: http://127.0.0.1:{port}/", output.getvalue())

            state["busy"].clear()
            other = state["units"] / "cse-preview-other-00000000.service"
            other.write_text(text.replace(str(repository), "/elsewhere"))
            unit.unlink()
            install()
            self.assertNotEqual(port, MANUSCRIPT.service_port(unit))
            with self.assertRaises(MANUSCRIPT.ManuscriptError):
                install(port=port)

            unit.write_text("[Service]\nExecStart=/bin/true\n")
            with self.assertRaises(MANUSCRIPT.ManuscriptError):
                install()
            self.assertEqual("[Service]\nExecStart=/bin/true\n", unit.read_text())

    def test_service_requires_project_python_and_names_missing_modules_before_installing(self):
        with self.preview_service() as state:
            state["missing"] = True
            with self.assertRaisesRegex(MANUSCRIPT.ManuscriptError, "No module named 'jupyter_cache'"):
                state["install"]()
            state["python"].unlink()
            with self.assertRaisesRegex(MANUSCRIPT.ManuscriptError, "project interpreter is missing.*jupyter_core"):
                state["install"]()
            with self.assertRaisesRegex(MANUSCRIPT.ManuscriptError, "interpreter must belong to this project"):
                state["install"](interpreter=state["base"] / "cache/bin/python")
            self.assertEqual([], state["systemctl"])
            self.assertFalse(state["units"].exists())

    def test_preview_service_refuses_unit_unsafe_manuscript_and_path_values(self):
        with self.preview_service() as state:
            for character in (" ", "\t", '"', "'", "\\", "%", "$", "\n", "\r"):
                with self.subTest(character=repr(character)):
                    root = state["repository"] / f"an{character}x"
                    root.mkdir()
                    with self.assertRaisesRegex(MANUSCRIPT.ManuscriptError, "manuscript path"):
                        state["install"](root=root)
                    quarto = f"/opt/q{character}x/quarto"
                    with (patch.object(MANUSCRIPT.shutil, "which", return_value=quarto),
                          self.assertRaisesRegex(MANUSCRIPT.ManuscriptError, "PATH entry")):
                        state["install"]()
            self.assertEqual([], list(state["units"].glob("*")) if state["units"].exists() else [])

    def test_preview_service_reports_a_started_unit_that_does_not_answer(self):
        with self.preview_service() as state, patch.object(MANUSCRIPT, "answering", return_value=False):
            status, output = state["install"]()
            self.assertEqual(1, status)
            self.assertIn("started, not answering at http://127.0.0.1:", output)
            self.assertIn("journalctl --user -u cse-preview-repo-", output)

if __name__ == "__main__":
    unittest.main()
