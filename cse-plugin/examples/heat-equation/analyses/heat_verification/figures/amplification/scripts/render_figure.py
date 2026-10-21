"""Render stability and monotonicity behavior from retained factors."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

OUTPUT = Path(__file__).resolve().parents[1] / "output"
data = pd.read_csv(OUTPUT / "amplification.csv")
style = yaml.safe_load((OUTPUT / "amplification.mpl.yaml").read_text())["matplotlib"]

plt.rcParams.update(
    {
        "font.family": "serif",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.hashsalt": "cse-heat-equation-example",
    }
)
fig, ax = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)
ax.plot(data.diffusion_number, data.ftcs_factor, color="#0072B2", linewidth=2.0, label="FTCS")
ax.plot(
    data.diffusion_number,
    data.crank_nicolson_factor,
    color="#D55E00",
    linestyle="--",
    linewidth=2.0,
    label="Crank-Nicolson",
)
ax.axhline(0.0, color="#555555", linewidth=0.8)
ax.axhline(-1.0, color="#888888", linewidth=0.8, linestyle=":")
ax.axhline(1.0, color="#888888", linewidth=0.8, linestyle=":")
ax.axvline(0.5, color="#009E73", linewidth=1.2, linestyle="-.", label=r"$r=0.5$")
ax.set(title=style["title"], xlabel=style["xlabel"], ylabel=style["ylabel"], ylim=(-3.2, 1.2))
ax.grid(True, color="#d9d9d9", linewidth=0.7)
ax.legend(frameon=False, ncol=2)
for suffix, options in (
    ("svg", {"metadata": {"Date": None}}),
    ("png", {"dpi": 200, "metadata": {"Software": "cse-heat-equation-example"}}),
    ("pdf", {"metadata": {"CreationDate": None, "ModDate": None}}),
):
    fig.savefig(OUTPUT / f"amplification.{suffix}", bbox_inches="tight", **options)
plt.close(fig)
