from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


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
            root = Path(directory) / "analyses"
            root.mkdir()
            retired_unit = root / Path("preview").with_suffix(".service")
            retired_unit.write_text("older plugin copy\n")
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

            self.assertFalse(retired_unit.exists())
            self.assertEqual(sorted(MANUSCRIPT.TOOLING_FILES), sorted(replaced))
            for name in ("_quarto-presentation.yml", "render.sh", "manuscript.py"):
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
