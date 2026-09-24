from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "plugin/assets/workflow/analysis/example"
TEMPLATE = EXAMPLE / "Snakefile"
PRESENT_SPEC = importlib.util.spec_from_file_location("cse_present", EXAMPLE / "scripts/present.py")
assert PRESENT_SPEC and PRESENT_SPEC.loader
PRESENT = importlib.util.module_from_spec(PRESENT_SPEC)
PRESENT_SPEC.loader.exec_module(PRESENT)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png(red: int) -> bytes:
    """Return a valid one-pixel PNG so Quarto can render and embed it."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes([0, red, 0, 0]))) + chunk(b"IEND", b"")


def write_retained_set(root: Path, *, rate: float = 0.005, keep_inputs: bool = False) -> SimpleNamespace:
    """Write a hash-coherent retained set that present.py accepts, without running calculate.

    ``keep_inputs`` hashes the inputs already in ``root`` (a copied example).
    Each file is written to a temporary name and then replaced, with the summary
    last, so a watcher never sees a partial set.
    """
    paths = {
        "observations": "inputs/observations.csv", "parameters": "inputs/parameters.json",
        "environment": "inputs/environment.json", "script": "scripts/calculate.py",
        "helper": "scripts/cooling_fit.py", "summary": "results/fit_summary.json",
        "curve": "results/fit_curve.csv", "figure": "figures/cooling_fit.png",
        "residual_figure": "figures/cooling_residuals.png",
    }

    def write(relative: str, data: bytes) -> None:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_bytes(data)
        os.replace(temporary, target)

    if not keep_inputs:
        for name, content in (("observations", "time_s,temperature_degC\n0,90\n60,72.5\n"),
                              ("parameters", '{"ambient_temperature_degC": 22.0}\n'),
                              ("environment", '{"python": "3.13.14"}\n'),
                              ("script", "calculate\n"), ("helper", "helper\n")):
            write(paths[name], content.encode())
    write(paths["curve"], (
        "time_s,observed_temperature_degC,fitted_temperature_degC,residual_degC\n"
        "0,90,90,0\n60,72.5,72.4,0.1\n"
    ).encode())
    write(paths["figure"], png(200))
    write(paths["residual_figure"], png(100))
    summary = {
        "complete": True,
        "checks": {"rmse_below_data_scaled_bound": True, "refit_consistent": True},
        "environment": {"python": "3.13.14", "packages": {"numpy": "2.5.3"}},
        "parameters": {"ambient_temperature_degC": 22.0, "initial_temperature_degC": 90.0},
        "inputs": {f"{name}_sha256": sha256(root / paths[name])
                   for name in ("observations", "parameters", "environment", "script", "helper")},
        "fit": {
            "cooling_rate_per_s": rate, "cooling_rate_standard_error_per_s": rate / 100,
            "cooling_rate_ci95_per_s": [rate * 0.98, rate * 1.02], "time_constant_s": 1 / rate,
            "residual_rmse_degC": 0.1, "rmse_bound_degC": 3.4, "refit_difference_per_s": 1e-16,
            "refit_tolerance_per_s": 1e-12, "observation_count": 2, "degrees_of_freedom": 1,
        },
        "generated_files": {name: {"path": paths[name], "sha256": sha256(root / paths[name])}
                            for name in ("curve", "figure", "residual_figure")},
    }
    write(paths["summary"], (json.dumps(summary, indent=2) + "\n").encode())
    # Paths are relative to ``root``, as Snakemake passes them; run present from there.
    return SimpleNamespace(
        **paths, output="results/cooling_fit_include.qmd", values="results/cooling_fit_values.qmd",
        provenance="results/cooling_fit_provenance.qmd", views="results/cooling_fit_views.ipynb",
    )


def present_command(arguments: SimpleNamespace) -> list[str]:
    return [item for name, value in vars(arguments).items()
            for item in (f"--{name.replace('_', '-')}", value)]


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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arguments = write_retained_set(root)
            (root / arguments.script).write_text("changed\n")
            result = subprocess.run(
                [sys.executable, str(EXAMPLE / "scripts/present.py"), *present_command(arguments)],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("changed after the retained calculation", result.stderr)
            self.assertFalse((root / arguments.output).exists())

    def test_presentation_does_not_rewrite_unchanged_includes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arguments = write_retained_set(root)
            outputs = [root / getattr(arguments, name) for name in ("output", "values", "provenance", "views")]
            with contextlib.chdir(root):
                PRESENT.present(arguments)
                for output in outputs:
                    os.utime(output, ns=(1_000_000_000, 1_000_000_000))
                PRESENT.present(arguments)
            self.assertEqual([1_000_000_000] * 4, [output.stat().st_mtime_ns for output in outputs])

if __name__ == "__main__":
    unittest.main()
