"""Generate exact plotted fields for the solution overlay."""

from pathlib import Path

import pandas as pd

from heat_verification import reference_solution, solve_crank_nicolson, solve_ftcs

OUTPUT = Path(__file__).resolve().parents[1] / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)

intervals = 40
final_fo = 0.1
steps = intervals**2 // 4
ftcs = solve_ftcs(intervals, final_fo, steps)
cn = solve_crank_nicolson(intervals, final_fo, steps)

pd.DataFrame(
    {
        "xi": ftcs.xi,
        "reference": reference_solution(ftcs.xi, final_fo),
        "ftcs": ftcs.theta,
        "crank_nicolson": cn.theta,
        "final_fo": final_fo,
        "intervals": intervals,
        "steps": steps,
        "diffusion_number": ftcs.diffusion_number,
    }
).to_csv(OUTPUT / "solution_overlay.csv", index=False, float_format="%.17g")
