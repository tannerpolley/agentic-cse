from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "plugin/scripts/workflow/check_prose.py"
FIXTURE = ROOT / "tests/fixtures/prose"

DEFECTS = [
    ("main.tex:7", "abstract length: 47 words (limit 35)"),
    ("main.tex:7", "abstract opener: The control sample was scanned"),
    ("main.tex:8", "certainty words: verified, all, independent"),
    ("main.tex:9", "abstract roundoff: '2e-8'"),
    ("fragments/results.tex:12", "paragraph density: 7 values in 22 words"),
    ("fragments/results.tex:16", "paragraph length: 158 words (limit 150)"),
    ("fragments/results.tex:16", "long sentence: 62 words (limit 60)"),
    ("fragments/results.tex:29", "table cell length: 16 words (limit 12)"),
    ("fragments/results.tex:34", "table note length: 62 words (limit 60)"),
    ("fragments/results.tex:41", "caption length: 64 words (limit 60)"),
    ("fragments/results.tex:44", "caveat ending"),
    ("fragments/results.tex:44", "repeated clause in 3 files"),
    ("fragments/results.tex:47", "non-result wording 'did not converge'"),
    ("fragments/conclusions.tex:2", "repeated clause in 3 files"),
    ("fragments/conclusions.tex:3", "caveat ending"),
    ("extra.tex:2", "paragraph density: 1 value in 18 words"),
    ("extra.tex:3", "caveat ending"),
    ("extra.tex:3", "repeated clause in 3 files"),
]


class ManuscriptProseTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(directory) / "paper"
        shutil.copytree(FIXTURE, self.root)

    def run_checker(self, *options, paths=("extra.tex", "main.tex"), status=0):
        result = subprocess.run(
            [sys.executable, str(CHECKER), "--root", str(self.root), *options, *paths],
            cwd=self.root, text=True, capture_output=True,
        )
        self.assertEqual(status, result.returncode, result.stdout + result.stderr)
        return result.stdout

    def test_defective_and_corrected_manuscript(self):
        original = self.run_checker()
        warnings = [line for line in original.splitlines() if ": warning:" in line]
        self.assertEqual(len(DEFECTS), len(warnings), original)
        for line, (location, message) in zip(warnings, DEFECTS):
            self.assertIn(f"{location}: warning: {message}", line)
        self.assertEqual(1, original.count("external editorial approval requires inspection"))
        self.assertIn("Summary: 18 advisories (main 15, supplement 3), 0 terminology violations, 1 scan notice.", original)
        self.assertIn("Files: main.tex 4, fragments/results.tex 9, fragments/conclusions.tex 2, extra.tex 3.", original)
        for hidden in ("A1", "F2", "A3", "F4", "F6", "F7", "F8", "F9", "schema", "contract", "5e-8", "Li/Na/TBAC"):
            self.assertNotIn(hidden, original)
        self.assertNotIn("fragments/values.tex:", original)

        main = self.root / "main.tex"
        text = main.read_text()
        start, end = text.index(r"\begin{abstract}"), text.index(r"\end{abstract}")
        main.write_text(text[:start] + "\\begin{abstract}\nDoes coating a membrane increase water uptake at steady flow?\n"
                        "Tests with treated and untreated membranes showed higher uptake after coating.\n" + text[end:])
        results = self.root / "fragments/results.tex"
        preface = results.read_text().split(r"\end{tikzpicture}", 1)[0] + "\\end{tikzpicture}\n"
        results.write_text(preface + r"""
The coating increased uptake after the membrane reached steady flow.
\begin{table}
\begin{tabular}{ll}
Sample & Uptake \\
Coated & Higher than the reference \\
\end{tabular}
\begin{tablenotes}
\item[a] Both samples used the same inlet conditions.
\end{tablenotes}
\end{table}
\captionof{figure}{Uptake increased on the coated membrane at steady flow.}
""")
        (self.root / "fragments/conclusions.tex").write_text("Coating increased membrane uptake at steady flow.\n")
        (self.root / "extra.tex").write_text("\\section{Additional conditions}\nThe inlet pressure stayed fixed.\n")
        corrected = self.run_checker()
        self.assertEqual(1, corrected.count(": warning:"), corrected)
        self.assertIn("abstract opener: Does coating a membrane increase water uptake at steady flow?", corrected)
        self.assertIn("Summary: 1 advisory (main 1, supplement 0), 0 terminology violations, 1 scan notice.", corrected)

    def test_print_form_in_standalone_printing_commands(self):
        (self.root / "paper.tex").write_text(
            "\\section{Threshold at 1e-3}\n\\caption{Pressure at 2e-3}\n\\footnote{Calibration at 3e-3}\n"
        )
        output = self.run_checker(paths=("paper.tex",))
        for line in range(1, 4):
            self.assertIn(f"paper.tex:{line}: warning: print form '{line}e-3'", output)

    def test_paragraph_density_takes_precedence_over_sentence_density(self):
        dense = "The samples retained 1, 2,\n3, 4, and 5 grams.\n"
        background = (
            "The treated and reference membranes reached steady uptake under humid air.\n"
            "The measurements agreed within the calibration uncertainty at the outlet.\n"
        ) * 9
        for suffix, heading in (("tex", r"\section{Results}"), ("qmd", "# Results")):
            with self.subTest(suffix=suffix):
                name = f"paper.{suffix}"
                (self.root / name).write_text(heading + "\n" + dense + "\n" + background + dense)
                output = self.run_checker(paths=(name,))
                warnings = [line for line in output.splitlines() if "density:" in line]
                self.assertEqual(2, len(warnings), output)
                self.assertIn(f"{name}:2: warning: paragraph density:", warnings[0])
                self.assertIn(f"{name}:23: warning: numeric density:", warnings[1])

    def test_abstract_default_limit_and_unqualified_roundoff(self):
        (self.root / "paper.tex").write_text(
            "\\begin{abstract}\n" + "We measured uptake in coated membrane samples. " * 36
            + "\nThe value was $3 \\times 10^{-8}$.\n\\end{abstract}\n"
        )
        output = self.run_checker(paths=("paper.tex",))
        self.assertIn("abstract length: 255 words (limit 250)", output)
        self.assertIn("abstract roundoff: '3 × 10^ -8'", output)
        self.assertNotIn("roundoff-scale numerical detail", output)

    def test_since_keeps_changed_lines_and_full_manuscript_context(self):
        def git(*args):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

        git("init", "-q")
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Fixture")
        self.assertIn("Summary: 0 advisories", self.run_checker("--since", "HEAD"))
        article = self.root / "main.tex"
        article.write_text(article.read_text().replace("The experiment verified", "The experiment confirmed"))
        git("add", "main.tex")
        results = self.root / "fragments/results.tex"
        results.write_text(results.read_text().replace("high humidity calculation did not converge",
                                                       "high humidity calculation remains provisional"))
        conclusions = self.root / "fragments/conclusions.tex"
        conclusions.write_text(conclusions.read_text().replace("However, the effect", "In contrast, the effect"))
        (self.root / "new.tex").write_text("The result is not established.\n")
        output = self.run_checker("--since", "HEAD", paths=("extra.tex", "main.tex", "new.tex"))
        self.assertIn("main.tex:8: warning: certainty words: confirmed", output)
        self.assertIn("fragments/results.tex:47: warning: non-result wording 'provisional'", output)
        self.assertIn("fragments/conclusions.tex:2: warning: repeated clause in 3 files", output)
        self.assertIn("new.tex:1: warning: non-result wording 'not established'", output)
        self.assertNotIn("fragments/results.tex:44:", output)
        self.assertNotIn("extra.tex:", output)
        self.assertIn("Summary: 5 advisories", output)
        self.assertIn("configuration error:", self.run_checker("--since", "unknown-revision", status=2))

    def test_numerical_approval_requires_authority(self):
        style = self.root / "docs/scientific/writing/STYLE.md"
        style.write_text(style.read_text().replace("Example owner decision", ""))
        output = self.run_checker()
        self.assertIn("roundoff-scale numerical detail '5e-8'", output)
        self.assertEqual(1, output.count("malformed numerical-value approval"))

    def test_non_result_wording(self):
        for term in ("did not converge", "not established", "unconverged", "cause unknown", "provisional"):
            with self.subTest(term=term):
                (self.root / "paper.tex").write_text(f"Calculation status: {term}.\n")
                self.assertIn(f"non-result wording {term!r}", self.run_checker(paths=("paper.tex",)))

    def test_declarations_keep_existing_terminology_exit_contract(self):
        output = self.run_checker()
        self.assertIn("0 terminology violations", output)
        paper = self.root / "main.tex"
        paper.write_text(paper.read_text().replace(r"\section{Results}", r"\section{Results}" + "\nThe contract changed."))
        output = self.run_checker(status=1)
        self.assertEqual(1, output.count("avoid 'contract'"))
        self.assertIn("1 terminology violation", output)
