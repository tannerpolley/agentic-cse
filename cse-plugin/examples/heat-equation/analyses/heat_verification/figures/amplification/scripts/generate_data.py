"""Generate worst-grid-mode amplification factors over diffusion number."""

from pathlib import Path

import numpy as np
import pandas as pd

from heat_verification import amplification_factor

OUTPUT = Path(__file__).resolve().parents[1] / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)
domain = globals()["CASE"]["conditions"]["amplification_diffusion_number"]
r = np.linspace(domain["minimum"], domain["maximum"], domain["count"])
pd.DataFrame(
    {
        "diffusion_number": r,
        "ftcs_factor": amplification_factor("ftcs", np.pi, r),
        "crank_nicolson_factor": amplification_factor("crank-nicolson", np.pi, r),
    }
).to_csv(OUTPUT / "amplification.csv", index=False, float_format="%.17g")
