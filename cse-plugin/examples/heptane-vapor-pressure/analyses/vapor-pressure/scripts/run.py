"""Evaluate the unchanged published correlation, then present retained values."""

import csv
import json
from pathlib import Path
import sys

import numpy as np

from present import present


ANALYSIS = Path(__file__).resolve().parents[1]


def calculate(output):
    parameters = json.loads((ANALYSIS / "inputs/model.json").read_text())
    with (ANALYSIS / "inputs/measurements.csv").open() as stream:
        observations = list(csv.DictReader(stream))
    temperature = np.array([float(row["temperature_K"]) for row in observations])
    celsius = temperature - parameters["kelvin_offset"]
    selected = (celsius >= parameters["temperature_min_C"]) & (
        celsius <= parameters["temperature_max_C"]
    )
    if not np.any(selected):
        raise ValueError("No measurements lie in the published correlation domain")

    def pressure_mmHg(temperature_K):
        t_C = temperature_K - parameters["kelvin_offset"]
        return 10.0 ** (parameters["A"] - parameters["B"] / (parameters["C"] + t_C))

    temperature = temperature[selected]
    observed = np.array([float(row["pressure_kPa"]) for row in observations])[selected]
    model_mmHg = pressure_mmHg(temperature)
    predicted = model_mmHg * parameters["mmHg_to_kPa"]
    residual = predicted - observed
    curve_temperature = np.linspace(temperature.min(), temperature.max(), 151)
    curve_pressure = pressure_mmHg(curve_temperature) * parameters["mmHg_to_kPa"]
    if not all(np.all(np.isfinite(values) & (values > 0)) for values in (
        temperature, observed, predicted, curve_pressure
    )):
        raise ValueError("VP-1 did not return finite positive physical values")

    results = output / "results"
    results.mkdir(parents=True, exist_ok=True)
    with (results / "comparison.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow([
            "source_table", "source_row", "temperature_K", "temperature_C",
            "measured_kPa", "model_mmHg", "model_kPa", "residual_kPa",
            "relative_residual_percent", "expanded_pressure_uncertainty_kPa",
            "expanded_temperature_uncertainty_K",
        ])
        for i, source in enumerate(np.array(observations)[selected]):
            t_C = temperature[i] - parameters["kelvin_offset"]
            writer.writerow([
                source["source_table"], source["source_row"], temperature[i], t_C,
                observed[i], model_mmHg[i], predicted[i], residual[i],
                100 * residual[i] / observed[i], 0.3, 0.115 + 0.002 * abs(t_C),
            ])
    with (results / "model-curve.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["temperature_K", "model_kPa"])
        writer.writerows(zip(curve_temperature, curve_pressure))
    summary = {
        "points": int(selected.sum()),
        "excluded_source_rows": [
            int(row["source_row"]) for row, include in zip(observations, selected) if not include
        ],
        "max_absolute_residual_kPa": float(np.max(np.abs(residual))),
        "root_mean_square_residual_kPa": float(np.sqrt(np.mean(residual**2))),
        "mean_absolute_relative_residual_percent": float(np.mean(np.abs(residual / observed)) * 100),
    }
    (results / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    destination = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ANALYSIS
    calculate(destination)
    present(destination)
