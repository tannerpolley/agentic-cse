from __future__ import annotations

import numpy as np
import pytest

from heat_verification import (
    amplification_factor,
    field_errors,
    observed_orders,
    reference_solution,
    solve_crank_nicolson,
    solve_ftcs,
)


def test_reference_satisfies_declared_initial_and_boundary_conditions():
    xi = np.linspace(0.0, 1.0, 33)
    initial = reference_solution(xi, 0.0)
    later = reference_solution(xi, 0.1)

    np.testing.assert_allclose(initial, np.sin(np.pi * xi), atol=2.0e-16, rtol=0.0)
    assert initial[0] == initial[-1] == later[0] == later[-1] == 0.0
    assert later[16] == pytest.approx(np.exp(-(np.pi**2) * 0.1), rel=8.0e-16)


@pytest.mark.parametrize(
    ("method", "solver"),
    [("ftcs", solve_ftcs), ("crank-nicolson", solve_crank_nicolson)],
)
def test_solvers_reproduce_independent_single_mode_amplification(method, solver):
    intervals = 16
    final_fo = 0.1
    steps = 64
    result = solver(intervals, final_fo, steps)
    phase = np.pi / intervals
    sine_squared = np.sin(phase / 2.0) ** 2
    if method == "ftcs":
        factor = 1.0 - 4.0 * result.diffusion_number * sine_squared
    else:
        numerator = 1.0 - 2.0 * result.diffusion_number * sine_squared
        denominator = 1.0 + 2.0 * result.diffusion_number * sine_squared
        factor = numerator / denominator
    expected = factor**steps * reference_solution(result.xi, 0.0)
    roundoff_atol = 64.0 * np.finfo(np.float64).eps * steps

    np.testing.assert_allclose(
        result.theta,
        expected,
        atol=roundoff_atol,
        rtol=64.0 * np.finfo(np.float64).eps,
    )
    assert result.theta[0] == result.theta[-1] == 0.0
    assert result.max_linear_residual <= roundoff_atol


def test_ftcs_rejects_a_linearly_unstable_diffusion_number():
    with pytest.raises(ValueError, match="diffusion_number <= 0.5"):
        solve_ftcs(intervals=10, final_fo=0.1, steps=10)


def test_crank_nicolson_stability_does_not_imply_monotonicity():
    factor = float(amplification_factor("crank-nicolson", np.pi, 4.0))
    assert -1.0 < factor < 0.0
    assert abs(factor) < 1.0
    assert float(amplification_factor("ftcs", np.pi, 0.51)) < -1.0


@pytest.mark.parametrize("solver", [solve_ftcs, solve_crank_nicolson])
def test_combined_refinement_enters_the_second_order_regime(solver):
    errors = []
    for intervals in (10, 20, 40, 80):
        steps = intervals**2 // 4
        result = solver(intervals, final_fo=0.1, steps=steps)
        errors.append(field_errors(result.theta, reference_solution(result.xi, 0.1)).linf)

    assert np.all(np.diff(errors) < 0.0)
    orders = observed_orders(errors)
    order_drift_allowance = 2.0 * abs(orders[-1] - orders[-2])
    floating_allowance = 64.0 * np.finfo(np.float64).eps / errors[-1]
    assert abs(orders[-1] - 2.0) <= order_drift_allowance + floating_allowance
