from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "plugin/assets/workflow/analysis/example"
MANUSCRIPT = ROOT / "plugin/assets/visualize/project/quarto/manuscript.py"
_FIXTURE_SPEC = importlib.util.spec_from_file_location("cse_snakemake_fixture", ROOT / "tests/test_snakemake_template.py")
assert _FIXTURE_SPEC and _FIXTURE_SPEC.loader
FIXTURE = importlib.util.module_from_spec(_FIXTURE_SPEC)
_FIXTURE_SPEC.loader.exec_module(FIXTURE)


class RenderingBehaviorTests(unittest.TestCase):
    def run_script(self, path: str, *args: str, env: dict[str, str] | None = None, cwd: Path = ROOT):
        return subprocess.run(
            ["bash", str(ROOT / path), *args] if path.endswith(".sh") else [sys.executable, str(ROOT / path), *args],
            cwd=cwd, env=env or os.environ.copy(), text=True, capture_output=True, check=False,
        )

    def test_beamer_starter_wraps_title_and_bookmarks_each_frame(self):
        for tool in ("lualatex", "kpsewhich", "mutool", "pdftotext"):
            if not shutil.which(tool):
                self.skipTest(f"{tool} is unavailable")
        for package in ("beamerthememoloch.sty", "bookmark.sty"):
            if subprocess.run(["kpsewhich", package], capture_output=True).returncode:
                self.skipTest(f"{package} is unavailable")

        title = "How do the experimental measurements and the reference model compare across the full temperature range?"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            header = ROOT / "plugin/assets/visualize/project/beamer/deck-header.tex"
            shutil.copyfile(header, project / header.name)
            (project / "deck.tex").write_text(rf"""
\documentclass[aspectratio=169]{{beamer}}
\input{{deck-header.tex}}
\begin{{document}}
\begin{{frame}}[t]{{Reference case}}
Body text.
\end{{frame}}
\begin{{frame}}[t]{{{title}}}
Body text.
\only<2>{{Second overlay.}}
\end{{frame}}
\end{{document}}
""", encoding="utf-8")
            build = subprocess.run(
                ["lualatex", "-interaction=nonstopmode", "-halt-on-error", "deck.tex"],
                cwd=project, capture_output=True, text=True,
            )
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            self.assertNotIn("Overfull", (project / "deck.log").read_text(encoding="utf-8"))

            outline = subprocess.check_output(["mutool", "show", "deck.pdf", "outline"], cwd=project, text=True)
            self.assertEqual([("Reference case", "1"), (title, "2")], re.findall(r'"([^"]+)"\s+#page=(\d+)', outline))

            extracted = subprocess.check_output(["pdftotext", "-layout", "deck.pdf", "-"], cwd=project, text=True)
            first, second, overlay = [[line.strip() for line in page.splitlines() if line.strip()]
                                      for page in extracted.rstrip("\f").split("\f")]
            self.assertEqual(["Reference case", "Body text.", "1"], first)
            self.assertEqual(title, " ".join(second[:2]))
            self.assertEqual(["Body text.", "2"], second[2:])
            self.assertIn("Second overlay.", " ".join(overlay))
            self.assertEqual("2", overlay[-1])

    def test_matplotlib_project_style_renders_scoped_group_mapping(self):
        if importlib.util.find_spec("matplotlib") is None:
            self.skipTest("matplotlib is required for the selected style rendering check")
        import warnings
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib.colors import to_rgb

        source = ROOT / "plugin/assets/visualize/project/matplotlib/cse.mplstyle"
        x = np.linspace(0, 1, 41)
        observed_x = x[::8].copy()
        curves = [np.exp(-x) + group for group in range(4)]
        observations = [y[::8].copy() + 0.03 for y in curves]
        deck = {
            "figure.figsize": (12, 5), "font.size": 22, "axes.labelsize": 22,
            "axes.titlesize": 24, "xtick.labelsize": 20, "ytick.labelsize": 20,
            "legend.fontsize": 20, "lines.linewidth": 2.5, "lines.markersize": 8,
        }
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            style = project / "docs/scientific/figures/cse.mplstyle"
            style.parent.mkdir(parents=True)
            shutil.copyfile(source, style)
            with warnings.catch_warnings(record=True) as caught, self.assertNoLogs("matplotlib", level="WARNING"):
                warnings.simplefilter("always")
                loaded = matplotlib.rc_params_from_file(style, fail_on_error=True, use_default_template=False)
                before = {key: plt.rcParams[key] for key in loaded}
                for name, overrides in (("manuscript", {}), ("deck", deck)):
                    with self.subTest(placement=name), plt.style.context(style):
                        plt.rcParams.update(overrides)
                        groups = dict(zip(range(4), plt.rcParams["axes.prop_cycle"]))
                        background = np.array(to_rgb(plt.rcParams["axes.facecolor"]))
                        def luminance(rgb):
                            linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
                            return float(linear @ [0.2126, 0.7152, 0.0722])
                        for entry in groups.values():
                            light, dark = sorted((luminance(np.array(to_rgb(entry["color"]))), luminance(background)))
                            self.assertGreaterEqual((dark + 0.05) / (light + 0.05), 3)
                        fig, ax = plt.subplots()
                        try:
                            lines, points = [], []
                            for group, entry in groups.items():
                                curve_style = {**entry, "marker": "None"}
                                point_style = {**entry, "linestyle": "None"}
                                line, = ax.plot(x, curves[group], **curve_style)
                                point, = ax.plot(observed_x, observations[group], **point_style)
                                lines.append(line)
                                points.append(point)
                                np.testing.assert_array_equal(x, line.get_xdata())
                                np.testing.assert_array_equal(curves[group], line.get_ydata())
                                np.testing.assert_array_equal(observed_x, point.get_xdata())
                                np.testing.assert_array_equal(observations[group], point.get_ydata())
                                self.assertEqual("None", line.get_marker())
                                self.assertEqual("None", point.get_linestyle())
                                self.assertEqual(line.get_color(), point.get_color())
                                self.assertEqual("none", point.get_markerfacecolor())
                            self.assertEqual(4, len({line.get_linestyle() for line in lines}))
                            self.assertEqual(4, len({point.get_marker() for point in points}))
                            ax.set_xlabel("Time (s)")
                            ax.set_ylabel("Synthetic response (mol kg⁻¹)")
                            for extension in ("png", "pdf"):
                                output = project / f"{name}.{extension}"
                                fig.savefig(output)
                                self.assertGreater(output.stat().st_size, 0)
                            np.testing.assert_array_equal(fig.get_size_inches(), overrides.get("figure.figsize", (3.4, 2.55)))
                            self.assertEqual(overrides.get("font.size", 10), plt.rcParams["font.size"])
                        finally:
                            plt.close(fig)
                    self.assertEqual(before, {key: plt.rcParams[key] for key in loaded})
                # A preserved project customization overrides the shipped starter.
                project_override = project / "project.mplstyle"
                project_override.write_text("font.size: 13\nlines.linewidth: 2\n")
                with plt.style.context([style, project_override]):
                    self.assertEqual(13, plt.rcParams["font.size"])
                    self.assertEqual(2, plt.rcParams["lines.linewidth"])
                self.assertEqual(before, {key: plt.rcParams[key] for key in loaded})
                self.assertEqual([], [str(warning.message) for warning in caught])

    def test_example_analysis_renders_and_refreshes_changed_retained_value(self):
        if not shutil.which("quarto") or not shutil.which("snakemake"):
            self.skipTest("quarto and snakemake are required for the example site render")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "analyses"
            analysis = root / "cooling-fit"
            shutil.copytree(EXAMPLE, analysis, ignore=shutil.ignore_patterns(
                "results", "figures", ".snakemake", "__pycache__"))
            shutil.copyfile(EXAMPLE / "article.qmd", root / "index.qmd")
            FIXTURE.write_retained_set(analysis, rate=0.005, keep_inputs=True)

            def run(command, cwd=root):
                result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

            notebook = analysis / "notebook.qmd"
            notebook.write_text(notebook.read_text().replace(
                "resources:\n", "execute:\n  enabled: true\nresources:\n", 1)
                + '\n```{python}\nraise RuntimeError("render ran Python")\n```\n')
            (root / "unregistered.qmd").write_text("# Unregistered\n")
            run(["snakemake", "--cores", "1", "present"], analysis)
            run([sys.executable, str(MANUSCRIPT), "init", "."])
            run([sys.executable, "manuscript.py", "include", ".", "cooling-fit/notebook.qmd",
                 "--title", "Cooling-rate fit", "--group", "Cooling studies"])
            run(["bash", str(root / "render.sh")], root.parent)
            self.assertFalse((root / "_site/unregistered.html").exists())

            for target in ("index.html", "cooling-fit/notebook.html"):
                page = (root / "_site" / target).read_text()
                sidebar = re.search(r'<nav id="quarto-sidebar".*?</nav>', page, re.DOTALL)[0]
                for title in ("Home", "Cooling-rate fit", "Cooling studies"):
                    self.assertIn(f'menu-text">{title}<', sidebar)
                self.assertNotRegex(sidebar, r'href="[^"]*\.html#')
                self.assertIn('id="TOC"', page)
                for label in ("fig-cooling-fit", "fig-cooling-residuals", "tbl-cooling-parameters", "eq-cooling-model"):
                    self.assertIn(f'id="{label}"', page)
                self.assertIn(r"5.000 \times 10^{-3}", page)

            FIXTURE.write_retained_set(analysis, rate=0.0071, keep_inputs=True)
            run([sys.executable, "manuscript.py", "refresh", ".", "cooling-fit/notebook.qmd"])
            for target in ("index.html", "cooling-fit/notebook.html"):
                self.assertIn(r"7.100 \times 10^{-3}", (root / "_site" / target).read_text())


if __name__ == "__main__":
    unittest.main()
