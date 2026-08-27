"""Generate every retained numerical table without rendering figures."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GENERATORS = (
    ROOT / "analyses/heat_verification/figures/solution_overlay/scripts/generate_data.py",
    ROOT / "analyses/heat_verification/figures/refinement/scripts/generate_data.py",
    ROOT / "analyses/heat_verification/figures/amplification/scripts/generate_data.py",
)
CASE = json.loads(
    (ROOT / "analyses/heat_verification/inputs/case.json").read_text(encoding="utf-8")
)

for generator in GENERATORS:
    runpy.run_path(str(generator), init_globals={"CASE": CASE}, run_name="__main__")
