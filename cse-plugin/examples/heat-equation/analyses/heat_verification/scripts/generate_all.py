"""Generate every retained numerical table without rendering figures."""

from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GENERATORS = (
    ROOT / "analyses/heat_verification/figures/solution_overlay/scripts/generate_data.py",
    ROOT / "analyses/heat_verification/figures/refinement/scripts/generate_data.py",
    ROOT / "analyses/heat_verification/figures/amplification/scripts/generate_data.py",
)

for generator in GENERATORS:
    runpy.run_path(str(generator), run_name="__main__")
