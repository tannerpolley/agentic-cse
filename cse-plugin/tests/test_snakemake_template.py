from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "plugin/assets/workflow/analysis/Snakefile"
EXAMPLE = ROOT / "plugin/assets/workflow/analysis/example"
PRESENT_SPEC = importlib.util.spec_from_file_location("cse_present", EXAMPLE / "scripts/present.py")
assert PRESENT_SPEC and PRESENT_SPEC.loader
PRESENT = importlib.util.module_from_spec(PRESENT_SPEC)
PRESENT_SPEC.loader.exec_module(PRESENT)


def branch(text: str, mode: str) -> str:
    start = text.index(f'if _MODE == "{mode}":')
    if mode == "present":
        end = text.index("\nelse:\n", start)
        return text[start:end]
    return text[text.index("\nelse:\n", start) + 1:]


def rule_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^    rule {name}:\n", text)
    if match is None:
        raise AssertionError(f"rule {name!r} is missing")
    next_rule = re.search(r"(?m)^    rule \w+:\n", text[match.end():])
    end = match.end() + (next_rule.start() if next_rule else len(text[match.end():]))
    return text[match.start():end]


class SnakemakeTemplateTests(unittest.TestCase):
    def test_presentation_branch_has_no_calculation_rule_ancestor(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        present = branch(text, "present")
        calculation = text[text.index("\nelse:\n") + 1:]
        self.assertIn("rule present:", present)
        self.assertNotIn("rule calculate:", present)
        self.assertIn("rule calculate:", calculation)

        # The active presentation graph contains only rules declared in its
        # branch; no calculation producer can therefore become an ancestor.
        present_rules = set(re.findall(r"(?m)^    rule (\w+):$", present))
        self.assertEqual({"present"}, present_rules)
        self.assertNotIn("calculate", present_rules)

    def test_rule_outputs_are_named_generated_files(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        calculation = text[text.index("\nelse:\n") + 1:]
        for rule_text, name in ((branch(text, "present"), "present"), (calculation, "calculate")):
            outputs = rule_block(rule_text, name).split("        output:", 1)[1]
            outputs = outputs.split("        shell:", 1)[0]
            self.assertNotRegex(outputs, r"['\"]inputs/")
            self.assertNotIn("notebook.qmd", outputs)

    def test_example_scripts_referenced_by_snakefile_exist(self):
        text = (EXAMPLE / "Snakefile").read_text(encoding="utf-8")
        scripts = set(re.findall(r"['\"](scripts/[^'\"]+\.py)['\"]", text))
        self.assertTrue(scripts)
        for relative in scripts:
            self.assertTrue((EXAMPLE / relative).is_file(), relative)

    def test_presentation_refuses_calculation_script_changed_after_calculation(self):
        def sha256(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "inputs"
            results = root / "results"
            figures = root / "figures"
            inputs.mkdir()
            results.mkdir()
            figures.mkdir()
            observations = inputs / "observations.csv"
            parameters = inputs / "parameters.json"
            environment = inputs / "environment.json"
            scripts = root / "scripts"
            scripts.mkdir()
            script = scripts / "calculate.py"
            helper = scripts / "cooling_fit.py"
            observations.write_text("time,temperature\n0,90\n")
            parameters.write_text('{"ambient": 22}\n')
            environment.write_text('{"python": "3.13.14"}\n')
            script.write_text("original\n")
            helper.write_text("helper\n")
            curve = results / "fit_curve.csv"
            figure = figures / "cooling_fit.png"
            curve.write_text("time,observed,fitted\n0,90,90\n")
            figure.write_bytes(b"figure")
            summary = results / "fit_summary.json"
            summary.write_text(json.dumps({
                "complete": True,
                "checks": {"rmse": True},
                "inputs": {
                    "observations_sha256": sha256(observations),
                    "parameters_sha256": sha256(parameters),
                    "environment_sha256": sha256(environment),
                    "script_sha256": sha256(script),
                    "helper_sha256": sha256(helper),
                },
                "fit": {"cooling_rate_per_s": 0.005, "residual_rmse_degC": 0.1},
                "generated_files": {
                    "curve": {"path": curve.as_posix(), "sha256": sha256(curve)},
                    "figure": {"path": figure.as_posix(), "sha256": sha256(figure)},
                },
            }))
            script.write_text("changed\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(EXAMPLE / "scripts/present.py"),
                    "--observations", str(observations),
                    "--parameters", str(parameters),
                    "--environment", str(environment),
                    "--script", str(script),
                    "--helper", str(helper),
                    "--summary", str(summary),
                    "--curve", str(curve),
                    "--figure", str(figure),
                    "--output", str(results / "cooling_fit_include.qmd"),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("changed after the retained calculation", result.stderr)
            self.assertFalse((results / "cooling_fit_include.qmd").exists())

    def test_presentation_does_not_rewrite_an_unchanged_include(self):
        def sha256(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "inputs"
            results = root / "results"
            figures = root / "figures"
            scripts = root / "scripts"
            for path in (inputs, results, figures, scripts):
                path.mkdir()
            observations = inputs / "observations.csv"
            parameters = inputs / "parameters.json"
            environment = inputs / "environment.json"
            script = scripts / "calculate.py"
            helper = scripts / "cooling_fit.py"
            curve = results / "fit_curve.csv"
            figure = figures / "cooling_fit.png"
            summary = results / "fit_summary.json"
            output = results / "cooling_fit_include.qmd"
            for path, content in (
                (observations, "time,temperature\n0,90\n"),
                (parameters, '{"ambient": 22}\n'),
                (environment, '{"python": "3.13.14"}\n'),
                (script, "calculate\n"),
                (helper, "helper\n"),
                (curve, "curve\n"),
            ):
                path.write_text(content)
            figure.write_bytes(b"figure")
            summary.write_text(json.dumps({
                "complete": True,
                "checks": {"rmse": True},
                "inputs": {
                    "observations_sha256": sha256(observations),
                    "parameters_sha256": sha256(parameters),
                    "environment_sha256": sha256(environment),
                    "script_sha256": sha256(script),
                    "helper_sha256": sha256(helper),
                },
                "fit": {"cooling_rate_per_s": 0.005, "residual_rmse_degC": 0.1},
                "generated_files": {
                    "curve": {"path": curve.as_posix(), "sha256": sha256(curve)},
                    "figure": {"path": figure.as_posix(), "sha256": sha256(figure)},
                },
            }))
            arguments = SimpleNamespace(
                observations=observations,
                parameters=parameters,
                environment=environment,
                script=script,
                helper=helper,
                summary=summary,
                curve=curve,
                figure=figure,
                output=output,
            )
            PRESENT.present(arguments)
            os.utime(output, ns=(1_000_000_000, 1_000_000_000))
            before = output.stat().st_mtime_ns
            PRESENT.present(arguments)
            self.assertEqual(before, output.stat().st_mtime_ns)


if __name__ == "__main__":
    unittest.main()
