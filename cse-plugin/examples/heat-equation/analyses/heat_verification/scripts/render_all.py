"""Render every retained figure from its generated table."""

from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RENDERERS = (
    ROOT / "analyses/heat_verification/figures/solution_overlay/scripts/render_figure.py",
    ROOT / "analyses/heat_verification/figures/refinement/scripts/render_figure.py",
    ROOT / "analyses/heat_verification/figures/amplification/scripts/render_figure.py",
)

for renderer in RENDERERS:
    runpy.run_path(str(renderer), run_name="__main__")
