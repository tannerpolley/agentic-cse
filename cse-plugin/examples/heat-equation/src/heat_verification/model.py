"""Declared FTCS and Crank-Nicolson discretizations for one verification case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import solve_banded

Method = Literal["ftcs", "crank-nicolson"]


@dataclass(frozen=True)
class SimulationResult:
    """Final field and numerical conditions for one uniform-grid calculation."""

    method: Method
    xi: NDArray[np.float64]
    theta: NDArray[np.float64]
    final_fo: float
    intervals: int
    steps: int
    delta_xi: float
    delta_fo: float
    diffusion_number: float
    max_linear_residual: float


def _conditions(
    intervals: int,
    final_fo: float,
    steps: int,
) -> tuple[NDArray[np.float64], float, float, float]:
    if isinstance(intervals, bool) or not isinstance(intervals, int) or intervals < 2:
        raise ValueError("intervals must be an integer greater than or equal to 2")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
        raise ValueError("steps must be a positive integer")
    if not np.isfinite(final_fo) or final_fo <= 0.0:
        raise ValueError("final_fo must be finite and positive")
    xi = np.linspace(0.0, 1.0, intervals + 1, dtype=np.float64)
    delta_xi = 1.0 / intervals
    delta_fo = float(final_fo) / steps
    diffusion_number = delta_fo / delta_xi**2
    return xi, delta_xi, delta_fo, diffusion_number


def reference_solution(
    xi: NDArray[np.float64] | list[float] | float,
    fourier_number: float,
) -> NDArray[np.float64]:
    """Evaluate REF-FOURIER-001 on the declared dimensionless basis."""
    points = np.asarray(xi, dtype=np.float64)
    if not np.all(np.isfinite(points)) or np.any((points < 0.0) | (points > 1.0)):
        raise ValueError("xi values must be finite and lie in [0, 1]")
    if not np.isfinite(fourier_number) or fourier_number < 0.0:
        raise ValueError("fourier_number must be finite and nonnegative")
    values = np.exp(-(np.pi**2) * fourier_number) * np.sin(np.pi * points)
    return np.where((points == 0.0) | (points == 1.0), 0.0, values)


def semidiscrete_reference(intervals: int, fourier_number: float) -> NDArray[np.float64]:
    """Evaluate the exact-in-time first sine mode of the centered spatial operator."""
    if isinstance(intervals, bool) or not isinstance(intervals, int) or intervals < 2:
        raise ValueError("intervals must be an integer greater than or equal to 2")
    if not np.isfinite(fourier_number) or fourier_number < 0.0:
        raise ValueError("fourier_number must be finite and nonnegative")
    xi = np.linspace(0.0, 1.0, intervals + 1, dtype=np.float64)
    delta_xi = 1.0 / intervals
    eigenvalue = -4.0 * np.sin(np.pi / (2.0 * intervals)) ** 2 / delta_xi**2
    values = np.exp(eigenvalue * fourier_number) * np.sin(np.pi * xi)
    values[[0, -1]] = 0.0
    return values


def amplification_factor(
    method: Method,
    phase: NDArray[np.float64] | list[float] | float,
    diffusion_number: NDArray[np.float64] | list[float] | float,
) -> NDArray[np.float64]:
    """Evaluate the independently recorded discrete Fourier-mode oracle."""
    mu = np.asarray(phase, dtype=np.float64)
    r = np.asarray(diffusion_number, dtype=np.float64)
    if np.any(~np.isfinite(mu)) or np.any(~np.isfinite(r)) or np.any(r < 0.0):
        raise ValueError(
            "phase and diffusion_number must be finite; diffusion_number is nonnegative"
        )
    mode_term = np.sin(mu / 2.0) ** 2
    if method == "ftcs":
        return 1.0 - 4.0 * r * mode_term
    if method == "crank-nicolson":
        return (1.0 - 2.0 * r * mode_term) / (1.0 + 2.0 * r * mode_term)
    raise ValueError(f"unsupported method: {method}")


def solve_ftcs(intervals: int, final_fo: float, steps: int) -> SimulationResult:
    """Solve M-FTCS-001 with exact zero-boundary enforcement."""
    xi, delta_xi, delta_fo, r = _conditions(intervals, final_fo, steps)
    if r > 0.5:
        raise ValueError(f"FTCS requires diffusion_number <= 0.5; received {r:.17g}")
    theta = reference_solution(xi, 0.0)
    for _ in range(steps):
        updated = theta.copy()
        updated[1:-1] = theta[1:-1] + r * (theta[:-2] - 2.0 * theta[1:-1] + theta[2:])
        updated[[0, -1]] = 0.0
        theta = updated
    return SimulationResult(
        method="ftcs",
        xi=xi,
        theta=theta,
        final_fo=float(final_fo),
        intervals=intervals,
        steps=steps,
        delta_xi=delta_xi,
        delta_fo=delta_fo,
        diffusion_number=r,
        max_linear_residual=0.0,
    )


def solve_crank_nicolson(intervals: int, final_fo: float, steps: int) -> SimulationResult:
    """Solve M-CN-001 with a SciPy tridiagonal banded solve."""
    xi, delta_xi, delta_fo, r = _conditions(intervals, final_fo, steps)
    interior_size = intervals - 1
    lhs = np.zeros((3, interior_size), dtype=np.float64)
    lhs[0, 1:] = -0.5 * r
    lhs[1, :] = 1.0 + r
    lhs[2, :-1] = -0.5 * r

    theta = reference_solution(xi, 0.0)
    max_residual = 0.0
    for _ in range(steps):
        old = theta[1:-1]
        rhs = (1.0 - r) * old + 0.5 * r * (theta[:-2] + theta[2:])
        new = solve_banded((1, 1), lhs, rhs, check_finite=False)
        residual = (1.0 + r) * new - rhs
        if interior_size > 1:
            residual[:-1] -= 0.5 * r * new[1:]
            residual[1:] -= 0.5 * r * new[:-1]
        max_residual = max(max_residual, float(np.max(np.abs(residual), initial=0.0)))
        theta[1:-1] = new
        theta[[0, -1]] = 0.0
    return SimulationResult(
        method="crank-nicolson",
        xi=xi,
        theta=theta,
        final_fo=float(final_fo),
        intervals=intervals,
        steps=steps,
        delta_xi=delta_xi,
        delta_fo=delta_fo,
        diffusion_number=r,
        max_linear_residual=max_residual,
    )
