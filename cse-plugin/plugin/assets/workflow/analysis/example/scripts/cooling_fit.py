"""Numerical owner for the deterministic one-parameter cooling fit."""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares
from scipy.stats import t as student_t


def temperature(time_s: np.ndarray, cooling_rate_per_s: float, ambient: float, initial: float) -> np.ndarray:
    return ambient + (initial - ambient) * np.exp(-cooling_rate_per_s * time_s)


def fit_rate(
    time_s: np.ndarray,
    observed_temperature: np.ndarray,
    *,
    ambient: float,
    initial: float,
    initial_guesses: tuple[float, float],
) -> dict[str, object]:
    def residual(parameter: np.ndarray) -> np.ndarray:
        return temperature(time_s, float(parameter[0]), ambient, initial) - observed_temperature

    fits = [
        least_squares(residual, x0=[guess], bounds=(0.0, np.inf),
                      xtol=1e-14, ftol=1e-14, gtol=1e-14)
        for guess in initial_guesses
    ]
    if not all(fit.success for fit in fits):
        raise ValueError("the positive cooling-rate fit did not converge from every start")

    cooling_rate = float(fits[0].x[0])
    refit_rate = float(fits[1].x[0])
    fitted_temperature = temperature(time_s, cooling_rate, ambient, initial)
    residual_temperature = observed_temperature - fitted_temperature
    rmse = float(np.sqrt(np.mean(residual_temperature ** 2)))

    # Linearized standard error from the Jacobian at the optimum. It assumes
    # independent, equal-variance temperature errors and treats the ambient and
    # initial temperatures as exact, so it omits their contribution.
    degrees_of_freedom = time_s.size - 1
    if degrees_of_freedom < 1:
        raise ValueError("the standard error needs at least two observations")
    jacobian = fits[0].jac[:, 0]
    residual_variance = float(np.sum(residual_temperature ** 2)) / degrees_of_freedom
    standard_error = float(np.sqrt(residual_variance / np.dot(jacobian, jacobian)))
    half_width = float(student_t.ppf(0.975, degrees_of_freedom)) * standard_error

    # Both checks scale from this data set and fitted quantity; no external
    # benchmark value or solver tolerance is an acceptance oracle.
    rmse_bound = max(float(np.ptp(observed_temperature)) * 0.05, np.finfo(float).eps)
    refit_difference = abs(cooling_rate - refit_rate)
    refit_tolerance = max(
        abs(cooling_rate) * 1e-9,
        np.finfo(float).eps * max(1.0, abs(cooling_rate)) * 100.0,
    )
    checks = {
        "rmse_below_data_scaled_bound": rmse < rmse_bound,
        "refit_consistent": refit_difference <= refit_tolerance,
    }

    return {
        "cooling_rate_per_s": cooling_rate,
        "refit_rate_per_s": refit_rate,
        "cooling_rate_standard_error_per_s": standard_error,
        "cooling_rate_ci95_per_s": [cooling_rate - half_width, cooling_rate + half_width],
        "time_constant_s": 1.0 / cooling_rate if cooling_rate > 0 else None,
        "observation_count": int(time_s.size),
        "degrees_of_freedom": degrees_of_freedom,
        "residual_rmse_degC": rmse,
        "rmse_bound_degC": rmse_bound,
        "refit_difference_per_s": refit_difference,
        "refit_tolerance_per_s": refit_tolerance,
        "rmse_below_data_scaled_bound": checks["rmse_below_data_scaled_bound"],
        "refit_consistent": checks["refit_consistent"],
        "fitted_temperature": fitted_temperature,
    }
