import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "plugin/assets/visualize/project/quarto/manuscript.py"


class QuartoManagerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.write("index.qmd", "# Synthesis\n")
        self.membership = self.root / "_cse-manuscript.json"

    def write(self, name, text):
        (self.root / name).write_text(text)

    def command(self, name, *arguments, status=0, env=None):
        result = subprocess.run([sys.executable, str(SCRIPT), name, ".", *arguments], cwd=self.root,
                                text=True, capture_output=True, env=env)
        self.assertEqual(status, result.returncode, result.stderr)
        return result

    def test_init_preserves_project_files_and_upgrades_old_sidebar(self):
        self.write("render.sh", "foreign")
        self.assertIn("refusing to overwrite", self.command("init", status=1).stderr)
        self.assertEqual("foreign", (self.root / "render.sh").read_text())
        (self.root / "render.sh").unlink()

        self.command("init")
        owned = {"_quarto.yml": "custom config", "site.css": "custom css", "index.qmd": "# Revised",
                 ".gitignore": (self.root / ".gitignore").read_text() + "local\n"}
        retired = ("preview.service", "_quarto-presentation.yml", ".cse-quarto-source.json")
        old_tooling = dict.fromkeys(("manuscript.py", "render.sh", *retired), "old")
        for name, content in {**owned, **old_tooling}.items():
            self.write(name, content)
        old_home = {"section": "Home", "contents": [{"text": "Overview", "href": "index.qmd"}]}
        title_page = {"text": "Title only", "href": "title.qmd"}
        old_report = {"section": "Report", "contents": [
            {"text": "Overview", "href": "report.qmd"}, {"text": "Results", "href": "report.qmd#results"}]}
        group = {"section": "Cases", "contents": [title_page, old_report]}
        self.write(self.membership.name, json.dumps({"project": {"render": ["index.qmd", "title.qmd", "report.qmd"]},
            "website": {"sidebar": {"contents": [old_home, group]}}, "cse-title-only": ["title.qmd"]}))
        self.command("init")
        state = json.loads(self.membership.read_text())
        self.assertEqual([{"text": "Home", "href": "index.qmd"}, {"section": "Cases", "contents": [
            title_page, {"text": "Report", "href": "report.qmd"}]}], state["website"]["sidebar"]["contents"])
        self.assertEqual(["index.qmd", "title.qmd", "report.qmd"], state["project"]["render"])
        self.assertFalse(any((self.root / name).exists() for name in retired))
        expected = {**owned, **{name: (SCRIPT.parent / name).read_text() for name in ("manuscript.py", "render.sh")}}
        self.assertEqual(expected, {name: (self.root / name).read_text() for name in expected})

    def test_include_moves_pages_and_removes_empty_groups(self):
        self.command("init")
        for name in ("first.qmd", "second.qmd"):
            self.write(name, "# Report\n")
            self.command("include", name, "--title", name, "--group", "Cases")
        self.command("include", "first.qmd", "--title", "First")
        state = json.loads(self.membership.read_text())
        self.assertEqual(["index.qmd", "second.qmd", "first.qmd"], state["project"]["render"])
        self.command("include", "second.qmd", "--title", "Second")
        state = json.loads(self.membership.read_text())
        contents = state["website"]["sidebar"]["contents"]
        self.assertEqual(["Home", "First", "Second"], [entry["text"] for entry in contents])
        self.assertEqual([entry["href"] for entry in contents], state["project"]["render"])
        for invalid in ("index.qmd", str(SCRIPT.parent / "example/notebook.qmd")):
            self.command("include", invalid, "--title", "Invalid", status=1)

    def test_refresh_uses_only_a_local_present_rule_and_stops_on_failure(self):
        self.command("init")
        (self.root / "case").mkdir()
        self.write("case/report.qmd", "# Report\n")
        self.command("include", "case/report.qmd", "--title", "Report")
        self.write("render.sh", 'echo "render $1"\n')
        self.write("snakemake", '#!/bin/bash\necho "${PWD##*/} $*"\nexit "$PRESENT_STATUS"\n')
        (self.root / "snakemake").chmod(0o755)
        env = {**os.environ, "PATH": f"{self.root}:{os.environ['PATH']}", "PRESENT_STATUS": "7"}
        rendered = "render ./case/report.qmd\nrender ./index.qmd\n"
        self.write("Snakefile", "ignored")
        self.assertEqual(rendered, self.command("refresh", "case/report.qmd", env=env).stdout)
        self.write("case/Snakefile", "local")
        present = "case --cores 1 --allowed-rules present -- present\n"
        self.assertEqual(present, self.command("refresh", "case/report.qmd", env=env, status=7).stdout)
        self.assertEqual(present + rendered, self.command("refresh", "case/report.qmd",
                                                         env={**env, "PRESENT_STATUS": "0"}).stdout)
