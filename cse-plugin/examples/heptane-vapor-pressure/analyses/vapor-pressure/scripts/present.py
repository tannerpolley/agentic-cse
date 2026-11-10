"""Render the one comparison and notebook fragments without running VP-1."""

import csv
import json
from pathlib import Path
import sys


def present(analysis):
    results = analysis / "results"
    with (results / "comparison.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    with (results / "model-curve.csv").open() as stream:
        curve = list(csv.DictReader(stream))
    summary = json.loads((results / "summary.json").read_text())

    # A fixed view of this one experiment keeps the renderer dependency-free.
    def x(temperature):
        return 80 + (float(temperature) - 300) / 20 * 550

    def y(pressure):
        return 340 - (float(pressure) - 6) / 12 * 270

    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="700" height="450" viewBox="0 0 700 450" role="img" aria-labelledby="title description">',
        '<title id="title">Heptane vapor pressure: unchanged correlation versus measurements</title>',
        '<desc id="description">Pressure in kPa against temperature in kelvin. Four experimental points with expanded measurement uncertainties and a continuous model line, over 303.2 to 318.2 K.</desc>',
        '<rect width="700" height="450" fill="white"/>',
        '<g font-family="sans-serif" font-size="15" fill="#222">',
        '<text x="80" y="28" font-size="18">Pure heptane: published model and independent data</text>',
    ]
    for temperature in (300, 305, 310, 315, 320):
        position = x(temperature)
        svg += [
            f'<path d="M{position},70 V340" stroke="#ddd"/>',
            f'<text x="{position}" y="366" text-anchor="middle">{temperature}</text>',
        ]
    for pressure in (6, 9, 12, 15, 18):
        position = y(pressure)
        svg += [
            f'<path d="M80,{position} H630" stroke="#ddd"/>',
            f'<text x="65" y="{position + 5}" text-anchor="end">{pressure}</text>',
        ]
    svg.append('<path d="M80,70 V340 H630" fill="none" stroke="#222"/>')
    points = " ".join(f'{x(row["temperature_K"]):.3f},{y(row["model_kPa"]):.3f}' for row in curve)
    svg.append(f'<polyline points="{points}" stroke="#0072B2" fill="none" stroke-width="2.5"/>')
    for row in rows:
        temperature, pressure = float(row["temperature_K"]), float(row["measured_kPa"])
        up = float(row["expanded_pressure_uncertainty_kPa"])
        ut = float(row["expanded_temperature_uncertainty_K"])
        px, py = x(temperature), y(pressure)
        svg += [
            f'<path d="M{px},{y(pressure-up)} V{y(pressure+up)} M{x(temperature-ut)},{py} H{x(temperature+ut)}" stroke="#222" stroke-width="1.5"/>',
            f'<circle cx="{px}" cy="{py}" r="4.5" fill="#222"/>',
        ]
    svg += [
        '<path d="M92,85 H122" stroke="#0072B2" stroke-width="2.5"/>',
        '<text x="132" y="90">Willingham et al. (1945), unchanged</text>',
        '<circle cx="107" cy="110" r="4.5" fill="#222"/>',
        '<text x="132" y="115">Busch et al. (2026), Table 2 rows 2–5</text>',
        '<text x="355" y="400" text-anchor="middle">Temperature (K)</text>',
        '<text transform="translate(22 205) rotate(-90)" text-anchor="middle">Vapor pressure (kPa)</text>',
        '<text x="80" y="432" font-size="13">Bars: reported expanded measurement uncertainties (k=2); rounding omitted.</text>',
        '</g></svg>\n',
    ]
    figures = analysis / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    (figures / "vapor-pressure.svg").write_text("\n".join(svg))

    table = [
        "| Table 2 row | Temperature (K) | Measured (kPa) | Model (kPa) | Model − measured (kPa) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        table.append(
            f'| {row["source_row"]} | {float(row["temperature_K"]):.1f} | '
            f'{float(row["measured_kPa"]):.1f} | {float(row["model_kPa"]):.3f} | '
            f'{float(row["residual_kPa"]):+.3f} |'
        )
    (results / "comparison.qmd").write_text("\n".join(table) + "\n")
    (results / "summary.qmd").write_text(
        f'The maximum absolute residual is **{summary["max_absolute_residual_kPa"]:.3f} kPa**, '
        f'the root mean square residual is **{summary["root_mean_square_residual_kPa"]:.3f} kPa**, '
        f'and the mean absolute relative residual is **{summary["mean_absolute_relative_residual_percent"]:.2f}%** '
        f'across {summary["points"]} measurements.\n'
    )


if __name__ == "__main__":
    present(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
