# Heat-equation verification study

This retained study separates three questions for the declared single-mode
heat equation:

1. Do FTCS and Crank-Nicolson reproduce the expected field at
   `Fo = 0.1`?
2. Do combined grid refinements at fixed `r = 0.4` approach the continuous
   reference at second order, and do isolated time refinements reproduce the
   first- and second-order time behavior of FTCS and Crank-Nicolson?
3. How does the worst-grid-mode amplification distinguish linear stability
   from monotonicity?

All inputs and outputs are dimensionless. The generated CSV tables are the
retained numerical record. Rendering reads those tables and does not rerun the
solvers. Figures are emitted as SVG, PNG, and PDF.

Run from the repository root:

```bash
uv run python analyses/heat_verification/scripts/generate_all.py
uv run python analyses/heat_verification/scripts/render_all.py
uv run python analyses/heat_verification/scripts/validate_results.py
```

The combined refinement uses interval counts 10, 20, 40, 80, and 160 with
`steps = N^2/4`, so `r = 0.4` exactly at `Fo = 0.1`. The temporal study uses
`N = 20`, compares with the exact-in-time centered-space first mode, and uses
80 through 1280 time steps. These conditions keep FTCS within `r <= 0.5`.

The finest-grid value tolerance is a 1.25 safety factor applied to the
factor-two Richardson remaining-error estimate, plus a 64-epsilon floating
allowance on the field scale. The order tolerance uses twice the change
between the two finest observed orders plus the propagated floating allowance.
Those rules are tied to this measured sequence; no project-wide `+/- 0.2` band
is used.
