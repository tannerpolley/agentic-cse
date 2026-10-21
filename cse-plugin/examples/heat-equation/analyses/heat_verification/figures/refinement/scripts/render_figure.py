"""Render convergence evidence from the retained refinement table."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

OUTPUT = Path(__file__).resolve().parents[1] / "output"
data = pd.read_csv(OUTPUT / "refinement.csv")
style = yaml.safe_load((OUTPUT / "refinement.mpl.yaml").read_text())["matplotlib"]

plt.rcParams.update(
    {
        "font.family": "serif",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.hashsalt": "cse-heat-equation-example",
    }
)
fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.2), constrained_layout=True)
styles = {
    "ftcs": {"color": "#0072B2", "marker": "o", "label": "FTCS"},
    "crank-nicolson": {"color": "#D55E00", "marker": "s", "label": "Crank-Nicolson"},
}
for ax, study, x_column, x_label in (
    (axes[0], "combined", "delta_xi", r"Grid spacing, $\Delta\xi$"),
    (axes[1], "temporal", "delta_fo", r"Time step, $\Delta Fo$"),
):
    for method, line_style in styles.items():
        subset = data[(data.study == study) & (data.method == method)]
        ax.loglog(subset[x_column], subset.linf_error, linewidth=1.8, **line_style)
    ax.set(xlabel=x_label, ylabel=r"$L^\infty$ field error")
    ax.grid(True, which="major", color="#d9d9d9", linewidth=0.7)
    ax.legend(frameon=False)
axes[0].set_title(style["combined_title"])
axes[1].set_title(style["temporal_title"])
fig.suptitle(style["title"])
for suffix, options in (
    ("svg", {"metadata": {"Date": None}}),
    ("png", {"dpi": 200, "metadata": {"Software": "cse-heat-equation-example"}}),
    ("pdf", {"metadata": {"CreationDate": None, "ModDate": None}}),
):
    fig.savefig(OUTPUT / f"refinement.{suffix}", bbox_inches="tight", **options)
plt.close(fig)
