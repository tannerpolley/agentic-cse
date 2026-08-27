"""Recompute scientific acceptance from the retained CSV tables."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
REFINEMENT = ROOT / "analyses/heat_verification/figures/refinement/output/refinement.csv"
AMPLIFICATION = ROOT / "analyses/heat_verification/figures/amplification/output/amplification.csv"
SOLUTION = ROOT / "analyses/heat_verification/figures/solution_overlay/output/solution_overlay.csv"
CASE = json.loads(
    (ROOT / "analyses/heat_verification/inputs/case.json").read_text(encoding="utf-8")
)
NOTEBOOK = ROOT / "analyses/heat_verification/notebook.qmd"

refinement = pd.read_csv(REFINEMENT, float_precision="round_trip")
solution = pd.read_csv(SOLUTION, float_precision="round_trip")
amplification = pd.read_csv(AMPLIFICATION, float_precision="round_trip")

failures: list[str] = []
conditions = CASE["conditions"]
if not np.allclose(refinement.final_fo, conditions["final_fo"]):
    failures.append("refinement results disagree with retained final_fo")
if sorted(refinement.loc[refinement.study == "combined", "intervals"].unique()) != sorted(
    conditions["combined_intervals"]
):
    failures.append("combined refinement intervals disagree with retained inputs")
if sorted(refinement.loc[refinement.study == "temporal", "steps"].unique()) != sorted(
    conditions["temporal_steps"]
):
    failures.append("temporal steps disagree with retained inputs")
if not np.allclose(solution.final_fo, conditions["final_fo"]):
    failures.append("solution overlay disagrees with retained final_fo")
if not np.all(solution.intervals == conditions["overlay_intervals"]):
    failures.append("solution overlay intervals disagree with retained inputs")
for study in ("combined", "temporal"):
    for method in ("ftcs", "crank-nicolson"):
        rows = refinement[(refinement.study == study) & (refinement.method == method)]
        errors = rows.linf_error.to_numpy()
        if not np.all(np.diff(errors) < 0.0):
            failures.append(f"{study}/{method}: L-infinity error is not monotonically decreasing")
        recomputed_orders = np.log2(errors[:-1] / errors[1:])
        finest = rows.iloc[-1]
        recomputed_order = recomputed_orders[-1]
        order_drift = abs(recomputed_orders[-1] - recomputed_orders[-2])
        binary64_allowance = 64.0 * np.finfo(np.float64).eps
        floating_order = binary64_allowance / errors[-1]
        recomputed_order_tolerance = 2.0 * order_drift + floating_order
        target_order = float(finest.target_order)
        order_accepted = abs(recomputed_order - target_order) <= recomputed_order_tolerance
        if not np.isclose(
            finest.observed_order_linf,
            recomputed_order,
            rtol=2.0e-13,
            atol=binary64_allowance,
        ):
            failures.append(f"{study}/{method}: stored finest order is stale")
        if not np.isclose(
            finest.order_tolerance,
            recomputed_order_tolerance,
            rtol=2.0e-13,
            atol=binary64_allowance,
        ):
            failures.append(f"{study}/{method}: stored order tolerance is stale")
        if bool(finest.order_accepted) != order_accepted or not order_accepted:
            failures.append(f"{study}/{method}: finest observed order failed its derived tolerance")

        # Every retained case is a single signed sine mode, so the coarse/fine
        # field difference equals the difference between their L-infinity errors.
        successive_difference = abs(errors[-2] - errors[-1])
        recomputed_value_tolerance = (
            1.25 * successive_difference / (2.0**target_order - 1.0)
            + binary64_allowance
        )
        value_accepted = errors[-1] <= recomputed_value_tolerance
        if not np.isclose(
            finest.value_tolerance,
            recomputed_value_tolerance,
            rtol=2.0e-13,
            atol=binary64_allowance,
        ):
            failures.append(f"{study}/{method}: stored Richardson value bound is stale")
        if bool(finest.value_accepted) != value_accepted or not value_accepted:
            failures.append(f"{study}/{method}: finest value failed its Richardson-derived bound")

if solution[["reference", "ftcs", "crank_nicolson"]].isna().any().any():
    failures.append("solution overlay contains non-finite values")
if not np.all(np.abs(amplification.crank_nicolson_factor) <= 1.0 + 8.0e-15):
    failures.append("Crank-Nicolson amplification exceeded the linear stability bound")
negative_cn = amplification.loc[amplification.diffusion_number > 0.5, "crank_nicolson_factor"]
if not np.all(negative_cn < 0.0):
    failures.append("Crank-Nicolson worst-mode factor did not become negative above r=0.5")

notebook = NOTEBOOK.read_text(encoding="utf-8")


def notebook_scientific(value: float) -> str:
    mantissa, exponent = f"{value:.6e}".split("e")
    return f"${mantissa}\\times10^{{{int(exponent)}}}$"


for study, method, label in (
    ("combined", "ftcs", "Combined | FTCS"),
    ("combined", "crank-nicolson", "Combined | Crank--Nicolson"),
    ("temporal", "ftcs", "Temporal | FTCS"),
    ("temporal", "crank-nicolson", "Temporal | Crank--Nicolson"),
):
    finest = refinement[(refinement.study == study) & (refinement.method == method)].iloc[-1]
    expected = (
        f"| {label} | {notebook_scientific(finest.linf_error)} | "
        f"{finest.observed_order_linf:.6f} |"
    )
    if expected not in notebook:
        failures.append(f"notebook retained-value row is stale: {study}/{method}")

if failures:
    raise SystemExit("\n".join(failures))

print("Retained heat-verification results passed scientific acceptance checks.")
