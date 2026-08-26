"""Render the solution overlay from its exact plotted-data snapshot."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

OUTPUT = Path(__file__).resolve().parents[1] / "output"
data = pd.read_csv(OUTPUT / "solution_overlay.csv")
style = yaml.safe_load((OUTPUT / "solution_overlay.mpl.yaml").read_text())["matplotlib"]

plt.rcParams.update(
    {
        "font.family": "serif",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.hashsalt": "cse-heat-equation-example",
    }
)
fig, ax = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)
ax.plot(data.xi, data.reference, color="#111111", linewidth=2.4, label="Continuous reference")
ax.plot(data.xi, data.ftcs, color="#0072B2", linestyle="--", linewidth=1.8, label="FTCS")
ax.plot(
    data.xi,
    data.crank_nicolson,
    color="#D55E00",
    linestyle=":",
    linewidth=2.2,
    label="Crank-Nicolson",
)
ax.set(title=style["title"], xlabel=style["xlabel"], ylabel=style["ylabel"])
ax.grid(True, color="#d9d9d9", linewidth=0.7)
ax.legend(frameon=False)
for suffix, options in (
    ("svg", {"metadata": {"Date": None}}),
    ("png", {"dpi": 200, "metadata": {"Software": "cse-heat-equation-example"}}),
    ("pdf", {"metadata": {"CreationDate": None, "ModDate": None}}),
):
    fig.savefig(OUTPUT / f"solution_overlay.{suffix}", bbox_inches="tight", **options)
plt.close(fig)
