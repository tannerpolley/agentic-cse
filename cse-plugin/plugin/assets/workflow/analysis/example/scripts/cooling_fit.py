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
    sensitivities_squared = [np.dot(fit.jac[:, 0], fit.jac[:, 0]) for fit in fits]
    eligible = [
        fit.success and 0 < sensitivity_squared < np.inf
        for fit, sensitivity_squared in zip(fits, sensitivities_squared)
    ]
    # Prefer a usable estimate, then lower residual cost. Break exact ties by rate.
    selected = min(range(len(fits)), key=lambda i: (not eligible[i], fits[i].cost, fits[i].x[0]))
    cooling_rate = float(fits[selected].x[0])
    refit_rate = float(fits[1 - selected].x[0])
    start_checks = {
        "first_start_converged": bool(fits[0].success),
        "second_start_converged": bool(fits[1].success),
    }
    fitted_temperature = temperature(time_s, cooling_rate, ambient, initial)
    residual_temperature = observed_temperature - fitted_temperature
    rmse = float(np.sqrt(np.mean(residual_temperature ** 2)))

    # Linearized standard error from the Jacobian at the optimum. It assumes
    # independent, equal-variance temperature errors and treats the ambient and
    # initial temperatures as exact, so it omits their contribution.
    degrees_of_freedom = time_s.size - 1
    standard_error = None
    interval = None
    rate_unavailable_reason = None
    uncertainty_unavailable_reason = None
    sensitivity_squared = sensitivities_squared[selected]
    if not fits[selected].success:
        rate_unavailable_reason = "The selected solver candidate did not converge."
    elif sensitivity_squared == 0:
        rate_unavailable_reason = "The fit returned a singular Jacobian at the candidate rate."
    elif not np.isfinite(sensitivity_squared):
        rate_unavailable_reason = "The fit returned a non-finite Jacobian norm at the candidate rate."
    elif degrees_of_freedom < 1:
        uncertainty_unavailable_reason = "The standard error needs at least two observations."
    else:
        residual_variance = float(np.sum(residual_temperature ** 2)) / degrees_of_freedom
        standard_error = float(np.sqrt(residual_variance / sensitivity_squared))
        half_width = float(student_t.ppf(0.975, degrees_of_freedom)) * standard_error
        interval = [cooling_rate - half_width, cooling_rate + half_width]

    # Agreement with data is reported, not gated: the RMSE is compared with the
    # observed temperature range because these observations carry no measurement
    # uncertainty. The illustrative refit target reports agreement across starts.
    # See Tolerances in the CSE numerical-testing reference for precision limits.
    observed_range = float(np.ptp(observed_temperature))
    refit_difference = abs(cooling_rate - refit_rate)
    refit_tolerance = max(
        abs(cooling_rate) * 1e-9,
        np.finfo(float).eps * max(1.0, abs(cooling_rate)) * 100.0,
    )

    return {
        "cooling_rate_per_s": None if rate_unavailable_reason else cooling_rate,
        "candidate_rate_per_s": cooling_rate if rate_unavailable_reason else None,
        "rate_unavailable_reason": rate_unavailable_reason,
        "refit_rate_per_s": refit_rate,
        "cooling_rate_standard_error_per_s": standard_error,
        "cooling_rate_ci95_per_s": interval,
        "uncertainty_unavailable_reason": uncertainty_unavailable_reason,
        "time_constant_s": 1.0 / cooling_rate if cooling_rate > 0 and not rate_unavailable_reason else None,
        "observation_count": int(time_s.size),
        "degrees_of_freedom": degrees_of_freedom,
        "residual_rmse_degC": rmse,
        "observed_range_degC": observed_range,
        "refit_difference_per_s": refit_difference,
        "refit_tolerance_per_s": refit_tolerance,
        "refit_consistent": refit_difference <= refit_tolerance,
        "start_checks": start_checks,
        "fitted_temperature": fitted_temperature,
    }
