from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class RenderingBehaviorTests(unittest.TestCase):
    def run_script(self, path: str, *args: str, env: dict[str, str] | None = None, cwd: Path = ROOT):
        return subprocess.run(
            ["bash", str(ROOT / path), *args] if path.endswith(".sh") else [sys.executable, str(ROOT / path), *args],
            cwd=cwd, env=env or os.environ.copy(), text=True, capture_output=True, check=False,
        )

    def test_quarto_preflight_preserves_original_and_rejects_competing_owner(self):
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

            real_quarto = shutil.which("quarto")
            if real_quarto is None:
                self.skipTest("quarto is unavailable")
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


if __name__ == "__main__":
    unittest.main()
