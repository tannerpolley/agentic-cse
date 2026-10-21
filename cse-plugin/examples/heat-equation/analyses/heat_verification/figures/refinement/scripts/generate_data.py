"""Generate combined and isolated-temporal refinement evidence."""

from pathlib import Path

import numpy as np
import pandas as pd

from heat_verification import (
    field_errors,
    observed_orders,
    reference_solution,
    richardson_error_bound,
    semidiscrete_reference,
    solve_crank_nicolson,
    solve_ftcs,
)

OUTPUT = Path(__file__).resolve().parents[1] / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)
CONDITIONS = globals()["CASE"]["conditions"]
FINAL_FO = CONDITIONS["final_fo"]
SOLVERS = {"ftcs": solve_ftcs, "crank-nicolson": solve_crank_nicolson}


def make_rows(study, method, results, references, resolutions, target_order):
    errors = [
        field_errors(result.theta, reference) for result, reference in zip(results, references)
    ]
    linf_orders = np.r_[np.nan, observed_orders([error.linf for error in errors])]
    rms_orders = np.r_[np.nan, observed_orders([error.rms for error in errors])]
    rows = []
    for index, (result, error, resolution) in enumerate(zip(results, errors, resolutions)):
        value_bound = np.nan
        value_accepted = False
        if index:
            value_bound = richardson_error_bound(
                results[index - 1].theta,
                result.theta,
                target_order,
            )
            value_accepted = error.linf <= value_bound
        order_tolerance = np.nan
        order_accepted = False
        if index >= 2:
            drift = abs(linf_orders[index] - linf_orders[index - 1])
            floating = 64.0 * np.finfo(np.float64).eps / error.linf
            order_tolerance = 2.0 * drift + floating
            order_accepted = abs(linf_orders[index] - target_order) <= order_tolerance
        rows.append(
            {
                "study": study,
                "method": method,
                "resolution": resolution,
                "intervals": result.intervals,
                "steps": result.steps,
                "delta_xi": result.delta_xi,
                "delta_fo": result.delta_fo,
                "diffusion_number": result.diffusion_number,
                "final_fo": result.final_fo,
                "linf_error": error.linf,
                "rms_error": error.rms,
                "observed_order_linf": linf_orders[index],
                "observed_order_rms": rms_orders[index],
                "target_order": target_order,
                "order_tolerance": order_tolerance,
                "order_accepted": order_accepted,
                "value_tolerance": value_bound,
                "value_accepted": value_accepted,
                "max_linear_residual": result.max_linear_residual,
            }
        )
    return rows


rows = []
combined_intervals = CONDITIONS["combined_intervals"]
for method, solver in SOLVERS.items():
    results = [
        solver(n, FINAL_FO, round(FINAL_FO * n**2 / CONDITIONS["combined_diffusion_number"]))
        for n in combined_intervals
    ]
    references = [reference_solution(result.xi, FINAL_FO) for result in results]
    rows.extend(make_rows("combined", method, results, references, combined_intervals, 2.0))

temporal_steps = CONDITIONS["temporal_steps"]
temporal_intervals = CONDITIONS["temporal_intervals"]
for method, solver in SOLVERS.items():
    results = [solver(temporal_intervals, FINAL_FO, steps) for steps in temporal_steps]
    references = [semidiscrete_reference(temporal_intervals, FINAL_FO) for _ in results]
    target_order = 1.0 if method == "ftcs" else 2.0
    rows.extend(make_rows("temporal", method, results, references, temporal_steps, target_order))

pd.DataFrame(rows).to_csv(OUTPUT / "refinement.csv", index=False, float_format="%.17g")
