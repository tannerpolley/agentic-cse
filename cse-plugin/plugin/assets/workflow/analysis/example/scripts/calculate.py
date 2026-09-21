"""Run the cooling fit and promote a checked result set atomically."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from cooling_fit import fit_rate, temperature


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_environment(path: Path) -> dict[str, object]:
    declared = json.loads(path.read_text(encoding="utf-8"))
    actual = {
        "python": platform.python_version(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("matplotlib", "numpy", "snakemake", "scipy")
        },
    }
    if declared != actual:
        raise ValueError(f"declared environment does not match the active uv environment: {actual}")
    return actual


def read_observations(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        expected = ["time_s", "temperature_degC"]
        if reader.fieldnames != expected:
            raise ValueError(f"expected columns {expected}, found {reader.fieldnames}")
        rows = list(reader)
    if not rows:
        raise ValueError("observations.csv is empty")
    time_s = np.array([float(row["time_s"]) for row in rows], dtype=float)
    observed = np.array([float(row["temperature_degC"]) for row in rows], dtype=float)
    if not np.all(np.isfinite(time_s)) or not np.all(np.isfinite(observed)):
        raise ValueError("observations contain a non-finite value")
    if np.any(time_s < 0) or np.any(np.diff(time_s) <= 0):
        raise ValueError("time_s must be strictly increasing and non-negative")
    return time_s, observed


def write_curve(path: Path, time_s: np.ndarray, observed: np.ndarray, fitted: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["time_s", "observed_temperature_degC", "fitted_temperature_degC"])
        writer.writerows(
            [f"{time:.12g}", f"{value:.12g}", f"{fit:.12g}"]
            for time, value, fit in zip(time_s, observed, fitted)
        )


def write_figure(path: Path, time_s: np.ndarray, observed: np.ndarray, *, rate: float, ambient: float, initial: float) -> None:
    dense_time = np.linspace(float(time_s[0]), float(time_s[-1]), 200)
    figure, axis = plt.subplots(figsize=(6.0, 4.0))
    axis.scatter(time_s, observed, color="#1f77b4", label="observations")
    axis.plot(
        dense_time,
        temperature(dense_time, rate, ambient, initial),
        color="#d62728",
        label="positive one-parameter fit",
    )
    axis.set_xlabel("time (s)")
    axis.set_ylabel("temperature (degC)")
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=120, metadata={"Software": "CSE cooling-fit example"})
    plt.close(figure)


def calculate(args: argparse.Namespace) -> None:
    observations_path = Path(args.observations)
    parameters_path = Path(args.parameters)
    environment_path = Path(args.environment)
    summary_path = Path(args.summary)
    curve_path = Path(args.curve)
    figure_path = Path(args.figure)

    time_s, observed = read_observations(observations_path)
    parameters = json.loads(parameters_path.read_text(encoding="utf-8"))
    environment = verify_environment(environment_path)
    ambient = float(parameters["ambient_temperature_degC"])
    initial = float(parameters["initial_temperature_degC"])
    guesses = tuple(float(value) for value in parameters["initial_guesses_per_s"])
    if len(guesses) != 2 or any(value <= 0 for value in guesses):
        raise ValueError("initial_guesses_per_s must contain two positive values")

    fit = fit_rate(
        time_s,
        observed,
        ambient=ambient,
        initial=initial,
        initial_guesses=guesses,
    )
    fitted = fit.pop("fitted_temperature")
    if not isinstance(fitted, np.ndarray):
        raise TypeError("fit owner did not return fitted temperatures")

    for path in (summary_path, curve_path, figure_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".cooling-fit-", dir=summary_path.parent) as directory:
        staging = Path(directory)
        staged_curve = staging / curve_path.name
        staged_figure = staging / figure_path.name
        staged_summary = staging / summary_path.name
        write_curve(staged_curve, time_s, observed, fitted)
        write_figure(
            staged_figure,
            time_s,
            observed,
            rate=float(fit["cooling_rate_per_s"]),
            ambient=ambient,
            initial=initial,
        )
        summary = {
            "complete": True,
            "model": "T(t) = T_ambient + (T_initial - T_ambient) exp(-k t)",
            "parameters": {
                "ambient_temperature_degC": ambient,
                "initial_temperature_degC": initial,
            },
            "environment": environment,
            "fit": {
                key: value
                for key, value in fit.items()
                if key != "fitted_temperature"
            },
            "checks": {
                "rmse_below_data_scaled_bound": fit["rmse_below_data_scaled_bound"],
                "refit_consistent": fit["refit_consistent"],
            },
            "inputs": {
                "observations_sha256": sha256(observations_path),
                "parameters_sha256": sha256(parameters_path),
                "environment_sha256": sha256(environment_path),
            },
            "generated_files": {
                "curve": {
                    "path": curve_path.as_posix(),
                    "sha256": sha256(staged_curve),
                },
                "figure": {
                    "path": figure_path.as_posix(),
                    "sha256": sha256(staged_figure),
                },
            },
        }
        staged_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        # The summary is promoted last and records hashes for the other files.
        # Keep a disposable copy of the previous set so a failed replacement
        # restores the last usable set instead of leaving mixed files behind.
        targets = (curve_path, figure_path, summary_path)
        backups = {}
        try:
            for index, target in enumerate(targets):
                if target.is_file():
                    backup = staging / f"previous-{index}"
                    shutil.copy2(target, backup)
                    backups[target] = backup
                else:
                    backups[target] = None
            os.replace(staged_curve, curve_path)
            os.replace(staged_figure, figure_path)
            os.replace(staged_summary, summary_path)
        except Exception:
            for target, backup in backups.items():
                if backup is not None and backup.exists():
                    os.replace(backup, target)
                elif target.exists():
                    target.unlink()
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", required=True)
    parser.add_argument("--parameters", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--curve", required=True)
    parser.add_argument("--figure", required=True)
    calculate(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
