import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


COMMAND = Path(__file__).resolve().parents[1] / "plugin/scripts/workflow/manuscript_health.py"


class ManuscriptHealthTests(unittest.TestCase):
    def test_records_worktree_changes_and_compares_archived_commits(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        repo = directory / "sample study"
        repo.mkdir()
        source = repo / "article.tex"
        config = directory / "config/cse/manuscripts.toml"
        config.parent.mkdir(parents=True)
        history = directory / "state/cse/manuscript-health.jsonl"
        env = {**os.environ, "XDG_CONFIG_HOME": str(directory / "config"), "XDG_STATE_HOME": str(directory / "state")}

        def git(*args):
            return subprocess.check_output(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
                cwd=repo, text=True, stderr=subprocess.PIPE,
            ).strip()

        def run_health(expected_status):
            result = subprocess.run([sys.executable, str(COMMAND)], env=env, cwd=directory,
                                    text=True, capture_output=True)
            self.assertEqual(expected_status, result.returncode, result.stdout + result.stderr)
            return result.stdout

        git("init", "-q")
        source.write_text("\\section{Pressure at 1e-3}\n\\section{Flow at 2e-3}\n")
        git("add", "article.tex")
        git("commit", "-qm", "Draft")
        bad = git("rev-parse", "HEAD")
        source.write_text("\\section{Pressure at 1e-3}\n")
        git("commit", "-qam", "Revise flow heading")
        good = git("rev-parse", "HEAD")
        config.write_text(f"""[[manuscripts]]
name = "Example"
root = {json.dumps(str(repo))}
path = "article.tex"

[[manuscripts.pairs]]
bad = "{bad}"
good = "{good}"
drops = ["print-form"]
""")

        first = run_health(0)
        self.assertIn(f"{bad[:9]}→{good[:9]}  PASS  print-form 2→1", first)
        edited = "\\section{Pressure}\n"
        source.write_text(edited)
        second = run_health(0)
        self.assertRegex(second, r"Example\s+0\s+-1\s+print-form 0 \(-1\)")
        self.assertIn("PASS  print-form 2→1", second)
        runs = [json.loads(line) for line in history.read_text().splitlines()]
        rows = [run["manuscripts"][str(source)] for run in runs]
        self.assertEqual([{"print-form": 1}, {}], [row["kinds"] for row in rows])
        self.assertEqual([good, good], [row["commit"] for row in rows])
        self.assertTrue(all(run["date"] for run in runs))

        config.write_text(config.read_text().replace('["print-form"]', '["abstract-opener"]'))
        output = run_health(1)
        self.assertIn("FAIL (abstract-opener did not drop)  abstract-opener 0→0, print-form 2→1", output)
        self.assertEqual(3, len(history.read_text().splitlines()))
        self.assertEqual(good, git("rev-parse", "HEAD"))
        self.assertEqual("article.tex", git("diff", "--name-only"))
        self.assertEqual("", git("diff", "--cached", "--name-only"))
        self.assertEqual(edited, source.read_text())
