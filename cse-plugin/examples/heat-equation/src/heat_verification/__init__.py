"""Numerical verification tools for the dimensionless heat equation."""

from .model import (
    SimulationResult,
    amplification_factor,
    reference_solution,
    semidiscrete_reference,
    solve_crank_nicolson,
    solve_ftcs,
)
from .verification import FieldErrors, field_errors, observed_orders, richardson_error_bound

__all__ = [
    "FieldErrors",
    "SimulationResult",
    "amplification_factor",
    "field_errors",
    "observed_orders",
    "reference_solution",
    "semidiscrete_reference",
    "richardson_error_bound",
    "solve_crank_nicolson",
    "solve_ftcs",
]
