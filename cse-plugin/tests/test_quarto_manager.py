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
                patch.object(MANUSCRIPT, "validate_root", return_value=state),
                patch.object(MANUSCRIPT, "notebook_argument", return_value="case/notebook.qmd"),
                patch.object(MANUSCRIPT, "prepare", side_effect=prepared),
                patch.object(MANUSCRIPT.subprocess, "run", side_effect=rendered) as run,
            ):
                self.assertEqual(0, MANUSCRIPT.refresh(root, notebook))

            self.assertEqual(["prepare", "render", "render"], events)
            self.assertEqual(
                [
                    ["quarto", "render", "case/notebook.qmd", "--profile", "presentation", "--cache-refresh"],
                    ["quarto", "render", "index.qmd", "--profile", "presentation", "--cache-refresh"],
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

    def test_preview_bridge_prepares_before_touching_and_keeps_stale_sources_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with (
                patch.object(MANUSCRIPT, "prepare", return_value=7) as prepare,
                patch.object(MANUSCRIPT, "touch_targets") as touch,
                contextlib.redirect_stderr(output),
            ):
                self.assertEqual(7, MANUSCRIPT.prepare_and_touch(root, {}, {root / "case" / "results.json"}))

            prepare.assert_called_once_with(root)
            touch.assert_not_called()
            self.assertIn("retained pages remain stale", output.getvalue())

    def test_changed_retained_file_notifies_its_notebook_and_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = {"manuscript": {"notebooks": [{"notebook": "case/notebook.qmd"}]}}
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

    def test_generated_and_cache_paths_are_not_watch_triggers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ignored = (
                ".snakemake/log.txt", ".cache/state", "tmp/file", "temp/file",
                "index.html.md", "index_files/image.png", "_site/page.html",
                "_freeze/page.json", "support/asset.bin",
            )
            for relative in ignored:
                with self.subTest(relative=relative):
                    self.assertFalse(MANUSCRIPT.is_watchable(root / relative, root))
            self.assertTrue(MANUSCRIPT.is_watchable(root / "case" / "notebook.qmd", root))

    def test_sigterm_cleans_up_the_fake_quarto_process_group(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "analyses"
            root.mkdir()
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
                "module.validate_root = lambda root: {'manuscript': {'notebooks': []}}\n"
                "module.presentation_workflows = lambda root: []\n"
                "raise SystemExit(module.preview(Path(sys.argv[1]), '127.0.0.1', 8000))\n"
            )
            environment = {
                **os.environ,
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                "FAKE_QUARTO_PID": str(pid_file),
            }
            process = subprocess.Popen(
                [sys.executable, str(runner), str(root)],
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            deadline = time.monotonic() + 5
            while not pid_file.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(pid_file.exists(), process.stderr.read() if process.poll() is not None else "")
            fake_pid = int(pid_file.read_text())
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(130, process.returncode, (stdout, stderr))
            with self.assertRaises(ProcessLookupError):
                os.kill(fake_pid, 0)

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


if __name__ == "__main__":
    unittest.main()
