from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request


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
                "if sys.argv[1] == 'inspect':\n"
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
                [sys.executable, str(script), "preview", str(root)],
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

    def test_example_analysis_renders_and_preview_shows_changed_retained_value(self):
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
            self.assertIn(r"5.000 \times 10^{-3}", notebook)
            self.assertEqual([], [p.name for p in (root / "_site").rglob("*preview*")])
            self.assertTrue((root / "_site/cooling-fit/results/fit_curve.csv").is_file())

            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            log = (root.parent / "preview.log").open("w")
            preview = subprocess.Popen(
                [sys.executable, "manuscript.py", "preview", ".", "--port", str(port)],
                cwd=root, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
            url = f"http://127.0.0.1:{port}/cooling-fit/notebook.html"

            def page() -> str:
                try:
                    with urllib.request.urlopen(url, timeout=5) as response:
                        return response.read().decode()
                except OSError:
                    return ""

            def wait_for(text: str, seconds: float) -> bool:
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    if preview.poll() is not None:
                        return False
                    if text in page():
                        return True
                    time.sleep(1)
                return False

            try:
                self.assertTrue(wait_for(r"5.000 \times 10^{-3}", 120), (root.parent / "preview.log").read_text())
                FIXTURE.write_retained_set(analysis, rate=0.0071, keep_inputs=True)
                self.assertTrue(wait_for(r"7.100 \times 10^{-3}", 60), (root.parent / "preview.log").read_text())
                # One change must settle: render byproducts must not re-trigger the bridge.
                time.sleep(15)
                settled = (root.parent / "preview.log").read_text().count("Output created")
                time.sleep(20)
                self.assertEqual(settled, (root.parent / "preview.log").read_text().count("Output created"))
            finally:
                if preview.poll() is None:
                    os.killpg(preview.pid, signal.SIGTERM)
                    try:
                        preview.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(preview.pid, signal.SIGKILL)
                        preview.wait()
                log.close()


if __name__ == "__main__":
    unittest.main()
