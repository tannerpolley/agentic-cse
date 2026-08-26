"""Metrics and refinement estimators used by tests and retained studies."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class FieldErrors:
    """Interior-grid field errors on the declared dimensionless scale."""

    linf: float
    rms: float


def field_errors(values: NDArray[np.float64], reference: NDArray[np.float64]) -> FieldErrors:
    """Return L-infinity and RMS errors over interior grid points."""
    computed = np.asarray(values, dtype=np.float64)
    expected = np.asarray(reference, dtype=np.float64)
    if computed.shape != expected.shape or computed.ndim != 1 or computed.size < 3:
        raise ValueError("values and reference must be matching one-dimensional grid fields")
    difference = computed[1:-1] - expected[1:-1]
    return FieldErrors(
        linf=float(np.max(np.abs(difference))),
        rms=float(np.sqrt(np.mean(difference**2))),
    )


def observed_orders(
    errors: NDArray[np.float64] | list[float],
    refinement_ratio: float = 2.0,
) -> NDArray[np.float64]:
    """Compute adjacent observed orders for positive refinement errors."""
    values = np.asarray(errors, dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or np.any(~np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError("errors must contain at least two positive finite values")
    if not np.isfinite(refinement_ratio) or refinement_ratio <= 1.0:
        raise ValueError("refinement_ratio must be finite and greater than one")
    return np.log(values[:-1] / values[1:]) / np.log(refinement_ratio)


def richardson_error_bound(
    coarse_values: NDArray[np.float64],
    fine_values: NDArray[np.float64],
    order: float,
    *,
    safety_factor: float = 1.25,
) -> float:
    """Bound the fine-grid error from nested-grid differences and roundoff."""
    coarse = np.asarray(coarse_values, dtype=np.float64)
    fine = np.asarray(fine_values, dtype=np.float64)
    if coarse.ndim != 1 or fine.ndim != 1:
        raise ValueError("coarse_values and fine_values must be one-dimensional fields")
    if not np.isfinite(order) or order <= 0.0 or safety_factor < 1.0:
        raise ValueError("order must be positive and safety_factor must be at least one")
    if fine.shape == coarse.shape:
        aligned_fine = fine
    elif fine.size == 2 * (coarse.size - 1) + 1:
        aligned_fine = fine[::2]
    else:
        raise ValueError("fields must share a grid or form a factor-two nested refinement")
    difference = float(np.max(np.abs(aligned_fine - coarse)))
    estimate = difference / (2.0**order - 1.0)
    scale = max(float(np.max(np.abs(fine))), 1.0)
    roundoff = 64.0 * np.finfo(np.float64).eps * scale
    return safety_factor * estimate + roundoff
