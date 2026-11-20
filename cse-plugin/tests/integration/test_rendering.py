from __future__ import annotations

import importlib.util
import json
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

    def test_title_only_sidebar_round_trip(self):
        if shutil.which("quarto") is None:
            self.skipTest("quarto is required")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "analyses"
            article = Path(directory) / "article.qmd"
            article.write_text("---\ntitle: Home\n---\n\n## Home heading\n")
            def run(*args):
                result = self.run_script(str(MANUSCRIPT), *map(str, args))
                self.assertEqual(0, result.returncode, result.stderr)
            run("init", root, "--article-source", article, "--source-commit", "a" * 40,
                "--runtime-tree-sha256", "b" * 64)
            page = root / "page.qmd"
            page.write_text("---\ntitle: Page\n---\n\n## First\n")
            run("include", root, page, "--title", "Overview", "--group", "Group", "--title-only")
            def check():
                state = json.loads((root / "_cse-manuscript.json").read_text())
                self.assertEqual([{"text": "Overview", "href": "page.qmd"}],
                                 state["website"]["sidebar"]["contents"][1]["contents"])
                self.assertEqual("Overview", state["website"]["sidebar"]["contents"][0]["contents"][0]["text"])
            check()
            page.write_text(page.read_text() + "\n## Second\n")
            run("sync", root)
            check()
            spec = importlib.util.spec_from_file_location("manuscript_roundtrip", MANUSCRIPT)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            state = json.loads((root / "_cse-manuscript.json").read_text())
            module.refresh_sections(root, state)
            self.assertEqual([{"text": "Overview", "href": "page.qmd"}],
                             state["website"]["sidebar"]["contents"][1]["contents"])
            run("validate", root)

    def test_quarto_preflight_preserves_original_and_rejects_competing_owner(self):
        real_quarto = shutil.which("quarto")
        if real_quarto is None:
            self.skipTest("quarto is unavailable; skipped native site preflight")
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "analyses"
            script = ROOT / "plugin/assets/visualize/project/quarto/manuscript.py"
            article = parent / "article.qmd"
            article.write_text("---\ntitle: Synthesis\n---\n\nRetained synthesis.\n")
            init_args = ["init", str(root), "--article-source", str(article),
                         "--source-commit", "a" * 40, "--runtime-tree-sha256", "b" * 64]
            initialized = self.run_script(str(script), *init_args)
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            (root / "_variables.yml").write_text("headline: retained\n")
            notebook = root / "result.qmd"
            notebook.write_text(
                "---\ntitle: Result\n---\n\n```{python}\n"
                "raise RuntimeError('cell must not execute during inspection')\n```\n"
            )
            included = self.run_script(
                str(script), "include", str(root), str(notebook), "--title", "Result"
            )
            self.assertEqual(0, included.returncode, included.stderr)

            def snapshot():
                return {
                    str(path.relative_to(parent)): (
                        str(path.readlink()) if path.is_symlink()
                        else None if path.is_dir() else path.read_bytes()
                    )
                    for path in parent.rglob("*")
                }

            before = snapshot()
            valid = self.run_script(str(script), "validate", str(root))
            self.assertEqual(0, valid.returncode, valid.stderr)
            self.assertEqual(before, snapshot())
            repeated = self.run_script(str(script), *init_args)
            self.assertEqual(0, repeated.returncode, repeated.stderr)
            self.assertEqual(before, snapshot())

            proxy_dir = parent / "bin"
            proxy_dir.mkdir()
            sentinel = parent / "unrequested-render"
            proxy = proxy_dir / "quarto"
            proxy.write_text(
                "#!/usr/bin/env python3\nimport os, pathlib, sys\n"
                "if sys.argv[1] in {'inspect', 'pandoc'}:\n"
                "    os.execv(os.environ['CSE_REAL_QUARTO'], [os.environ['CSE_REAL_QUARTO'], *sys.argv[1:]])\n"
                "pathlib.Path(os.environ['CSE_RENDER_SENTINEL']).write_text('executed')\n"
            )
            proxy.chmod(0o755)
            environment = {
                **os.environ, "PATH": f"{proxy_dir}{os.pathsep}{os.environ['PATH']}",
                "CSE_REAL_QUARTO": real_quarto, "CSE_RENDER_SENTINEL": str(sentinel),
            }
            config_path = root / "_quarto.yml"
            config = json.loads(config_path.read_text())
            config["project"]["pre-render"] = str(parent / "model.py")
            config_path.write_text(json.dumps(config, indent=2) + "\n")
            before = snapshot()
            commands = (
                [sys.executable, str(script), "validate", str(root)],
                [sys.executable, str(script), "refresh", str(root), str(notebook)],
                ["bash", "render.sh"],
            )
            for command in commands:
                result = subprocess.run(
                    command, cwd=root if command[0] == "bash" else parent, env=environment,
                    text=True, capture_output=True, check=False,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn(str(config_path), result.stderr)
                self.assertEqual(before, snapshot())
                self.assertFalse(sentinel.exists())

    def test_example_analysis_renders_and_refreshes_changed_retained_value(self):
        if shutil.which("quarto") is None or shutil.which("snakemake") is None:
            self.skipTest("quarto and snakemake are required for the example site render")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "analyses"
            analysis = root / "cooling-fit"
            shutil.copytree(EXAMPLE, analysis, ignore=shutil.ignore_patterns(
                "results", "figures", ".snakemake", "__pycache__"))
            # Retained outputs are written directly; the test never runs calculate.
            FIXTURE.write_retained_set(analysis, rate=0.005, keep_inputs=True)

            def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
                result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                return result

            run(["snakemake", "--cores", "1", "present"], analysis)
            run([sys.executable, str(MANUSCRIPT), "init", str(root), "--article-source", str(EXAMPLE / "article.qmd"),
                 "--source-commit", "a" * 40, "--runtime-tree-sha256", "b" * 64], root.parent)
            run([sys.executable, "manuscript.py", "include", ".", "cooling-fit/notebook.qmd",
                 "--title", "Cooling-rate fit", "--group", "Cooling studies/Exponential fits"], root)
            # Headings whose Pandoc anchors a text heuristic gets wrong; re-including must not duplicate.
            edge = root / "edge" / "notebook.qmd"
            edge.parent.mkdir()
            edge.write_text("---\ntitle: Edge\n# a yaml comment\n---\n\n::: {.callout-note}\n## Summary\nx\n:::\n\n"
                            "## Summary\n\n### Results\n\n## Results\n\n## The _cooling_ fit\n\n"
                            "## See [Smith](https://example.org)\n\n{{< include results/part.qmd >}}\n\n## Data\n")
            (edge.parent / "results").mkdir()
            (edge.parent / "results" / "part.qmd").write_text("## Data\n\nIncluded section.\n")
            for _ in range(2):
                run([sys.executable, "manuscript.py", "include", ".", "edge/notebook.qmd", "--title", "Edge"], root)
            edge.write_text(edge.read_text() + "\n## Added later\n")
            stale = subprocess.run([sys.executable, "manuscript.py", "validate", "."], cwd=root,
                                   text=True, capture_output=True, check=False)
            self.assertNotEqual(0, stale.returncode)
            self.assertIn("manuscript.py sync", stale.stderr)
            run([sys.executable, "manuscript.py", "sync", "."], root)
            membership = json.loads((root / "_cse-manuscript.json").read_text())
            self.assertEqual(1, membership["project"]["render"].count("edge/notebook.qmd"))
            edge_links = [c["text"] for c in membership["website"]["sidebar"]["contents"][-1]["contents"]]
            self.assertEqual(["Overview", "Summary", "Results", "The cooling fit", "See Smith", "Data", "Data",
                              "Added later"], edge_links)
            shortcode = root / "edge" / "shortcode.qmd"
            shortcode.write_text("---\ntitle: S\n---\n\n## Checks {{< meta title >}}\n")
            refused = subprocess.run([sys.executable, "manuscript.py", "include", ".", "edge/shortcode.qmd", "--title", "S"],
                                     cwd=root, text=True, capture_output=True, check=False)
            self.assertNotEqual(0, refused.returncode)
            self.assertIn("contains a shortcode", refused.stderr)
            shortcode.unlink()
            rendered = run(["bash", "render.sh"], root)
            self.assertNotIn("not found in resource path", rendered.stdout + rendered.stderr)

            article = (root / "_site/index.html").read_text(encoding="utf-8")
            notebook = (root / "_site/cooling-fit/notebook.html").read_text(encoding="utf-8")
            # Both pages are ordinary website pages: labels and cross-references resolve on each.
            for page in (article, notebook):
                for label in ("fig-cooling-fit", "fig-cooling-residuals", "tbl-cooling-parameters", "eq-cooling-model"):
                    self.assertIn(f'id="{label}"', page)
                for reference in ("Equation", "Figure", "Table"):
                    self.assertRegex(page, rf'class="quarto-xref">{reference}(&nbsp;|\s)1<')
                # One shared sidebar lists the home page and the notebook on every page.
                self.assertIn('id="quarto-sidebar"', page)
                self.assertIn('menu-text">Home<', page)
                self.assertIn('menu-text">Cooling-rate fit<', page)
                self.assertIn('menu-text">Cooling studies<', page)
                self.assertIn('menu-text">Exponential fits<', page)
                # No top bar: title, search, and reader mode live in the sidebar; math ships with the page.
                self.assertNotIn('class="navbar', page)
                self.assertIn("quarto-reader-toggle", page)
                self.assertIn("tabular-nums", page)
                self.assertNotIn("cdn.jsdelivr.net/npm/mathjax", page)
                self.assertNotIn("Back to Article", page)
                # The notebook is a collapsible sidebar section (caret) whose children are its headings;
                # no page table of contents or margin column takes width on the right.
                self.assertIn("sidebar-item-toggle", page)
                self.assertNotIn('id="TOC"', page)
                self.assertNotIn("column-margin", page)
            anchors = re.findall(r'href="\./cooling-fit/notebook\.html#([^"]+)"', article)
            self.assertIn("results", anchors)
            for anchor in anchors:
                self.assertIn(f'id="{anchor}"', notebook)
            edge_page = (root / "_site/edge/notebook.html").read_text(encoding="utf-8")
            edge_anchors = re.findall(r'href="\./edge/notebook\.html#([^"]+)"', article)
            self.assertEqual(["summary-1", "results-1", "the-cooling-fit", "see-smith", "data", "data-1", "added-later"],
                             edge_anchors)
            for anchor in edge_anchors:
                self.assertIn(f'id="{anchor}"', edge_page)
            self.assertIn(r"5.000 \times 10^{-3}", notebook)
            self.assertTrue((root / "_site/cooling-fit/results/fit_curve.csv").is_file())


            FIXTURE.write_retained_set(analysis, rate=0.0071, keep_inputs=True)
            run([sys.executable, "manuscript.py", "refresh", ".", "cooling-fit/notebook.qmd"], root)
            for page in ("index.html", "cooling-fit/notebook.html"):
                self.assertIn(r"7.100 \times 10^{-3}", (root / "_site" / page).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
