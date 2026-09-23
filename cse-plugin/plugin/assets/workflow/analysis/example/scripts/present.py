"""Prepare a Quarto include fragment from retained checked files only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def refuse(message: str) -> None:
    raise SystemExit(f"present refused retained outputs: {message}")


def present(args: argparse.Namespace) -> None:
    input_paths = {
        "observations_sha256": Path(args.observations),
        "parameters_sha256": Path(args.parameters),
        "environment_sha256": Path(args.environment),
        "script_sha256": Path(args.script),
        "helper_sha256": Path(args.helper),
    }
    summary_path = Path(args.summary)
    curve_path = Path(args.curve)
    figure_path = Path(args.figure)
    output_path = Path(args.output)
    if not summary_path.is_file():
        refuse(f"missing {summary_path}; run calculate before present")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("complete") is not True:
        refuse(f"{summary_path} is not marked complete")
    retained_inputs = summary.get("inputs", {})
    for name, path in input_paths.items():
        if not path.is_file():
            refuse(f"missing current input {path}")
        if sha256(path) != retained_inputs.get(name):
            refuse(f"{path} changed after the retained calculation; run calculate before present")
    checks = summary.get("checks", {})
    if not checks or not all(isinstance(value, bool) for value in checks.values()):
        refuse("the retained numerical checks are missing or malformed")

    generated = summary.get("generated_files", {})
    for name, path, expected_name in (
        ("curve", curve_path, "curve"),
        ("figure", figure_path, "figure"),
    ):
        record = generated.get(expected_name, {})
        if record.get("path") != path.as_posix():
            refuse(f"{name} path does not match the retained summary")
        if not path.is_file():
            refuse(f"missing {path}")
        if sha256(path) != record.get("sha256"):
            refuse(f"{path} does not match the retained summary hash")

    fit = summary.get("fit", {})
    required = {
        "cooling_rate_per_s": "s^-1",
        "residual_rmse_degC": "degC",
    }
    if any(quantity not in fit for quantity in required):
        refuse("the retained fit is missing a required quantity")

    checks_result = "passed" if all(checks.values()) else "not passed; retain as supported negative evidence"
    table = [
        "<!-- Generated from retained fit_summary.json and fit_curve.csv. -->",
        "## Cooling-rate fit",
        "",
        "| quantity | value | unit |",
        "| --- | ---: | --- |",
        f"| cooling rate k | {float(fit['cooling_rate_per_s']):.12g} | s^-1 |",
        f"| residual RMSE | {float(fit['residual_rmse_degC']):.12g} | degC |",
        f"| numerical checks | {checks_result} | -- |",
        "",
        "![Cooling fit](figures/cooling_fit.png)",
        "",
    ]
    content = "\n".join(table).encode()
    if output_path.is_file() and output_path.read_bytes() == content:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(content.decode())
    os.replace(temporary, output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", required=True)
    parser.add_argument("--parameters", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--helper", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--curve", required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--output", required=True)
    present(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
