from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
SKILLS = {
    "setup", "research", "diagnose", "design", "build", "analyze",
    "review", "write", "prose", "audit", "zotero", "data", "digitize",
    "plot", "tikz", "latex", "quarto", "beamer",
}


class PluginBehaviorTests(unittest.TestCase):
    def test_identifier_cli_visible_boundaries(self):
        cases = {
            '.tex': (r'''\caption{F2 and A1} \label{F3} % F4
F4-0 & \texttt{issue \#13} & \nolinkurl{commit abc123} commit abcdef
\texttt{docs/fit\_table.csv}
\cite[F6]{A8} \ref{F8} \includegraphics{docs/F9.png}
\href{https://host/docs/F8.py}{F5}
\ce{F8} \SI{A8}{F9} $F8$ \(A8\)
\begin{verbatim}
F8
\end{verbatim}
$$
F8
$$
''', ['F2', 'A1', 'F4-0', 'issue #13', 'commit abc123', 'commit abcdef', 'docs/fit_table.csv', 'F6', 'F5']),
            '.md': ('''# F2
> "A1" and `F4-0` [F5](docs/F8.py)
`git show F8` <!-- F8 --> [@F8] {#F8}
```python
F8
```
    F8
$F8$ [safe][F8]
[F8]: docs/F8.py
''', ['F2', 'A1', 'F4-0', 'F5']),
            '.qmd': ('''---
title: F2
subtitle: |
  A1
other: F8
---
```{python}
#| fig-cap: F4-0
print("F8")
```
''', ['F2', 'A1', 'F4-0']),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suffix, (text, expected) in cases.items():
                path = root / ('paper' + suffix)
                path.write_text(text + '\nCO2 H2O Li/Na TBAC/DA/TOPO PrOMMiS/IDAES https://host/docs/F8.py 10.1234/docs/F8.py\n')
                result = subprocess.run([sys.executable, str(PLUGIN / 'scripts/workflow/check_prose.py'), '--root', str(root), str(path)], capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                for value in expected:
                    self.assertIn(repr(value), result.stdout)
                self.assertNotIn('F8', result.stdout)
                self.assertIn('writing-editorial.md#reader-facing-identifiers', result.stdout)
                self.assertIn(f'{path}:2:', result.stdout)
                self.assertEqual(len(expected), result.stdout.count(': warning:'))
            path.write_text('The schema changed with F2.\n')
            result = subprocess.run([sys.executable, str(PLUGIN / 'scripts/workflow/check_prose.py'), str(path)], capture_output=True, text=True)
            self.assertEqual(1, result.returncode)
            self.assertIn('warning: run/fit label', result.stdout)

    def test_identifier_scientific_approval_isolation(self):
        sys.path.insert(0, str(PLUGIN / 'scripts/workflow'))
        from check_prose import identifier_warnings
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / name for name in ('one.md', 'two.md', 'plot.py')]
            for path in paths:
                path.write_text('ax.set(title="F2 F4-0 issue #13 docs/file.py")' if path.suffix == '.py' else 'F2 F4-0 issue #13 docs/file.py')
            style = root / 'docs/scientific/writing/STYLE.md'
            style.parent.mkdir(parents=True)
            style.write_text('''## One
Sources: one.md; plot.py
| Scope | Standing owner decision | Authority |
| --- | --- | --- |
| *.md; *.py | Approved scientific labels: `F2`; `F4` | Owner, dated |
| *.md | Approved scientific labels: `F4-0` | |
## Two
Sources: two.md
External brief pointer: editorial.md
''')
            result = '\n'.join(identifier_warnings(paths + [style], root=root))
            self.assertNotIn("one.md:1: warning: run/fit label 'F2'", result)
            self.assertNotIn("plot.py:1: warning: run/fit label 'F2'", result)
            self.assertIn("two.md:1: warning: run/fit label 'F2'", result)
            self.assertEqual(3, result.count("run/fit label 'F4-0'"))
            self.assertEqual(3, result.count("issue/PR 'issue #13'"))
            self.assertEqual(3, result.count("repository path 'docs/file.py'"))
            self.assertIn('malformed scientific-label approval', result)
            self.assertIn('external editorial approval', result)
            style.unlink()
            self.assertEqual(3, '\n'.join(identifier_warnings(paths, root=root)).count("run/fit label 'F2'"))

    def test_identifier_figure_and_deck_extraction(self):
        import zipfile
        sys.path.insert(0, str(PLUGIN / 'scripts/workflow'))
        from check_prose import identifier_warnings
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script, deck = root / 'plot.py', root / 'deck.pptx'
            script.write_text('''# F8
filename = "F8"
ax.set(title="F2", xlabel="A1")
ax.set_xticklabels(["F3", "F4-0"])
ax.text(0, 0, f"F5 {value}")
ax.annotate(dynamic)
ax.set_title(f"F{value}8")
ax.legend(labels=("A2",))
ax.plot(x, y, label="A3")
''')
            with zipfile.ZipFile(deck, 'w') as archive:
                archive.writestr('ppt/slides/slide1.xml', '<s xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:p><a:r><a:t>F</a:t></a:r><a:r><a:t>2</a:t></a:r></a:p><table><a:p><a:r><a:t>A1</a:t></a:r></a:p></table></s>')
                archive.writestr('docProps/core.xml', '<text>F8</text>')
            result = '\n'.join(identifier_warnings([script, deck], root=root))
            self.assertNotIn('F8', result)
            for value in ('F2', 'A1', 'F3', 'F4-0', 'F5', 'A2', 'A3'):
                self.assertIn(repr(value), result)
            self.assertEqual(3, result.count('dynamic figure label'))
            self.assertIn('deck.pptx:ppt/slides/slide1.xml:paragraph 1:', result)
            script.write_text('not valid python !')
            deck.write_bytes(b'broken zip')
            self.assertEqual(2, '\n'.join(identifier_warnings([script, deck], root=root)).count('incomplete scan:'))

    def test_numerical_advisories_flag_print_form_and_roundoff_detail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paper, notes, plot = root / 'paper.tex', root / 'notes.md', root / 'plot.py'
            paper.write_text(r'''The fit uses 2.4e-3 and 3 * 4 and 8k samples.
Masked $2.4e-3$ \num{2.4e-3} \qty{1e-3}{\metre} \SI{5e-3}{\second} \(1e-4\).
Charge residual (mol) & $-7.739\times 10^{-17}$ \\
One step lowers the objective by \num{6.6e-8}, above the tolerance.
The diffusivity is $1.9\times10^{-9}$ m$^2$/s and the rate constant is \num{3e-8}.
\definecolor{cseGreen}{HTML}{009E73} See docs/file.py.
''')
            notes.write_text('Interphase residuals agree to 7 × 10⁻¹².\nCode `1e-3` stays quiet; prose 1e-3 does not.\n')
            plot.write_text('x = 1e-3\nax.set_xlabel("rate 1e-3")\n')
            result = subprocess.run([sys.executable, str(PLUGIN / 'scripts/workflow/check_prose.py'), '--root', str(root), str(paper), str(notes), str(plot)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            out = result.stdout
            for value in ("'2.4e-3'", "'3 * 4'", "'8k'"):
                self.assertIn(f'paper.tex:1: warning: print form {value}', out)
            self.assertIn("notes.md:2: warning: print form '1e-3'", out)
            self.assertIn("plot.py:2: warning: print form '1e-3'", out)
            self.assertIn('scientific-writing.md#equations-quantities-and-units', out)
            self.assertEqual(5, out.count('print form'))
            for location in ('paper.tex:3:', 'paper.tex:4:', 'notes.md:1:'):
                self.assertIn(f'{location} warning: roundoff-scale numerical detail', out)
            self.assertEqual(3, out.count('roundoff-scale'))
            self.assertIn("repository path 'docs/file.py' ", out)

    def test_numeric_density_advisory_checks_sentences_outside_displays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paper, notes = root / 'paper.tex', root / 'notes.qmd'
            paper.write_text(r'''At 10 and 20 kPa, the yields were 3.2 and 4.1 g after 5 s.
The yield was 3.2 g after 5 s. The next run used 10, 20, and 30 kPa.
The four measurements were 1, 2, 3, and 4 with $x=5$ and \num{6} and \qty{7}{\second} \cite[8--9]{source2024}.
\begin{tabular}{rrrrr}
1 & 2 & 3 & 4 & 5 \\
\end{tabular}
\begin{tikzpicture}
\draw (1, 2) -- (3, 4) -- (5, 6);
\end{tikzpicture}
''')
            notes.write_text('''At 10 and 20 kPa,
the yields were 3.2 and 4.1 g after 5 s.

The four measurements were 1, 2, 3, and 4 [@source2024, pp. 5–6].

One | Two | Three | Four | Five
----|-----|-------|------|-----
1   | 2   | 3     | 4    | 5
''')
            result = subprocess.run([sys.executable, str(PLUGIN / 'scripts/workflow/check_prose.py'), '--root', str(root), str(paper), str(notes)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            warnings = [line for line in result.stdout.splitlines() if 'warning: numeric density' in line]
            self.assertEqual(2, len(warnings), result.stdout)
            for warning, location in zip(warnings, ('paper.tex:1:', 'notes.qmd:1:')):
                self.assertIn(location, warning)
                self.assertIn('scientific-writing.md#argument', warning)

    def test_numerical_advisories_are_quiet_on_shipped_examples(self):
        sys.path.insert(0, str(PLUGIN / 'scripts/workflow'))
        from check_prose import identifier_warnings
        result = '\n'.join(identifier_warnings([ROOT / 'examples'], root=ROOT / 'examples'))
        self.assertNotIn('print form', result)
        self.assertNotIn('roundoff-scale', result)


    def test_accepted_pi_reference_passes_prose_check(self):
        result = subprocess.run(
            [sys.executable, str(PLUGIN / "scripts/workflow/check_prose.py"),
             str(PLUGIN / "references/workflow/cse-pi-worker.md")],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_prose_check_keeps_fitting_regression_and_ignores_link_targets(self):
        sys.path.insert(0, str(PLUGIN / "scripts/workflow"))
        from check_prose import violations

        allowed = [
            "The joint regression fixes the MEA parameters.",
            "A parameter\nregression follows.",
            "The regression\nparameters are fixed.",
            "Weighted least-squares regression converged.",
            "The regression parameters and regression residuals are retained.",
            "The regressed parameters differ from the coupled-regression designs.",
            "Regression-based estimation uses the regression objective.",
            "The MEA–water interaction regressed against Cai data.",
            "See [the fitted table](results/regression_manifest-receipt.json).",
            "[ref]: docs/manifest.csv",
        ]
        flagged = [
            "The regression test passed.",
            "Run the regression suite.",
            "There is no regression.",
            "A regression in the solver output appeared.",
            "Two regressions remain.",
            "The solver regressed.",
            "The linear regression tests failed.",
            "See [the manifest](results/table.csv).",
            "[^1]: The regression test failed.",
        ]
        with tempfile.TemporaryDirectory() as directory:
            for index, text in enumerate(allowed + flagged):
                path = Path(directory) / f"case{index}.md"
                path.write_text(text + "\n", encoding="utf-8")
                self.assertEqual(index >= len(allowed), bool(violations([path])), text)

    def test_one_manifest_and_all_skills_use_cse_namespace(self):
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        references = {path.stem for path in (PLUGIN / "references").rglob("*.md")} | {"BANNED"}
        self.assertEqual("cse", manifest["name"])
        self.assertEqual(SKILLS, {path.name for path in (PLUGIN / "skills").iterdir()})
        self.assertFalse((ROOT / "extensions").exists())
        self.assertFalse((ROOT / ".codex-plugin").exists())
        self.assertEqual(
            {"name": "cse", "owner": {"name": "Tanner Polley"},
             "plugins": [{"name": "cse", "source": "./plugin"}]},
            json.loads((ROOT / ".claude-plugin/marketplace.json").read_text()),
        )
        self.assertEqual("cse", json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())["name"])
        root_catalog = json.loads((ROOT.parent / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual("cse", root_catalog["name"])
        self.assertEqual(["cse"], [entry["name"] for entry in root_catalog["plugins"]])
        self.assertEqual(PLUGIN, (ROOT.parent / root_catalog["plugins"][0]["source"]).resolve())
        for skill in SKILLS:
            frontmatter = yaml.safe_load((PLUGIN / "skills" / skill / "SKILL.md").read_text().split("---", 2)[1])
            self.assertEqual(skill, frontmatter["name"])
            self.assertIn("Use when", frontmatter["description"])
            self.assertLessEqual(len(frontmatter["description"]), 300)
            routing = frontmatter["metadata"]["cse-routing"]
            self.assertTrue(routing["direct"])
            for kind in ("direct", "conditional"):
                self.assertLessEqual(set(routing[kind]), references)
            codex = yaml.safe_load((PLUGIN / "skills" / skill / "agents/openai.yaml").read_text())
            self.assertEqual(
                not codex.get("policy", {}).get("allow_implicit_invocation", True),
                frontmatter.get("disable-model-invocation", False),
            )
            interface = codex["interface"]
            self.assertTrue(interface["display_name"])
            self.assertTrue(interface["short_description"])
            self.assertTrue(interface["default_prompt"].startswith("Use $cse:"))

    def test_active_payload_has_no_retired_namespaces_or_guards(self):
        text = "\n".join(path.read_text(errors="replace") for path in PLUGIN.rglob("*") if path.is_file()).casefold()
        for retired in ("cse-sources", "cse-visualize", "requires the core cse", "optional companion"):
            self.assertNotIn(retired, text)

    def test_two_phase_review_and_mode_doctrine_is_present(self):
        text = (PLUGIN / "README.md").read_text()
        for phrase in (
            "Research and design", "Execute and deliver", "Independent `review`",
            "Direct execution is the default",
        ):
            self.assertIn(phrase, text)
        phase_descriptions = {
            "setup": "Research and design", "research": "Research and design",
            "diagnose": "Research and design", "design": "Research and design",
            "build": "Execute and deliver", "analyze": "Execute and deliver",
            "write": "Execute and deliver",
        }
        for skill, phase in phase_descriptions.items():
            interface = yaml.safe_load((PLUGIN / "skills" / skill / "agents/openai.yaml").read_text())["interface"]
            self.assertNotIn("Workflow", interface["display_name"])
            self.assertIn(phase.replace(" or ", " / "), interface["display_name"])
        prose = yaml.safe_load((PLUGIN / "skills/prose/SKILL.md").read_text().split("---", 2)[1])
        self.assertEqual("supporting", prose["metadata"]["cse-kind"])
        workflow = (PLUGIN / "references/workflow/operating-model.md").read_text()
        normalized_workflow = " ".join(workflow.split())
        for phrase in (
            "CSE owns its scientific stages, evidence, and acceptance",
            "Direct execution is the default",
            "native host delegation",
        ):
            self.assertIn(phrase, normalized_workflow)
        self.assertNotIn("wait_threads", workflow)
        self.assertNotIn("send_message_to_thread", workflow)
        build = yaml.safe_load((PLUGIN / "skills/build/SKILL.md").read_text().split("---", 2)[1])
        self.assertIn("cse-pi-worker", build["metadata"]["cse-routing"]["conditional"])
        for skill in ("diagnose", "analyze", "review"):
            metadata = yaml.safe_load((PLUGIN / "skills" / skill / "SKILL.md").read_text().split("---", 2)[1])
            self.assertNotIn("cse-pi-worker", metadata["metadata"]["cse-routing"]["conditional"])
        self.assertFalse((PLUGIN / "references/workflow/execution-modes.md").exists())
        setup = (PLUGIN / "skills/setup/SKILL.md").read_text()
        self.assertIn("CSE execution mode: direct.", setup)
        self.assertNotIn("CSE execution mode: baton.", setup)
        projects = (PLUGIN / "references/workflow/analysis-sets.md").read_text()
        self.assertIn("required renderer executable", workflow)
        self.assertNotIn("Visualize is absent", projects)

    def test_issue_plan_and_prose_owners_are_explicit(self):
        github = (PLUGIN / "references/workflow/github-and-git.md").read_text()
        self.assertIn("issue body owns the complete current", github)
        self.assertIn("truncated output", github)
        self.assertIn("Preserve satisfied links", github)
        design = (PLUGIN / "skills/design/SKILL.md").read_text()
        self.assertIn("algorithms, or pseudocode", design)
        self.assertIn("Invoke `cse:review`", design)
        build = (PLUGIN / "skills/build/SKILL.md").read_text()
        self.assertIn("complete current issue body", build)
        self.assertIn("follow pagination", build)
        review = (PLUGIN / "skills/review/SKILL.md").read_text()
        self.assertIn("## Design readiness", review)
        self.assertIn("## Delivered review", review)
        self.assertNotIn("final manuscript", review.casefold())
        prose = (PLUGIN / "skills/prose/SKILL.md").read_text()
        self.assertIn("CSE prose is clear.", prose)
        self.assertIn("Prose does not edit", prose)
        self.assertIn("final manuscript check", prose)
        direct, conditional = "direct", "conditional"
        writing_routes = {
            "write": {direct: {"scientific-writing", "writing-editorial"},
                      conditional: {"manuscript-review", "latex-article-profiles"}},
            "prose": {direct: {"scientific-writing", "writing-editorial"}, conditional: {"manuscript-review"}},
            "review": {conditional: {"scientific-writing", "writing-editorial", "manuscript-review"}},
            "latex": {conditional: {"latex-article-profiles", "manuscript-review"}},
            "quarto": {conditional: {"latex-article-profiles"}},
            "beamer": {conditional: {"writing-editorial"}},
            "plot": {conditional: {"writing-editorial"}},
        }
        for skill, expected in writing_routes.items():
            text = (PLUGIN / f"skills/{skill}/SKILL.md").read_text()
            frontmatter = yaml.safe_load(text.split("---", 2)[1])
            routing = frontmatter["metadata"]["cse-routing"]
            for kind, references in expected.items():
                with self.subTest(skill=skill, kind=kind):
                    self.assertLessEqual(references, set(routing[kind]))
            if skill == "write":
                self.assertNotIn("latex-article-profiles", routing[direct])
        manuscript_routes = {
            "write": ("scientific-writing.md#fixing-a-review-finding",
                      "scientific-writing.md#emphasis-in-proportion",
                      "manuscript-review.md#story-spine-read"),
            "prose": ("scientific-writing.md#emphasis-in-proportion",
                      "manuscript-review.md#story-spine-read"),
            "review": ("manuscript-review.md#comparison-reconciliation",
                       "scientific-writing.md#shared-article-requirements"),
        }
        for skill, targets in manuscript_routes.items():
            body = (PLUGIN / "skills" / skill / "SKILL.md").read_text()
            for target in targets:
                with self.subTest(skill=skill, target=target):
                    self.assertIn(f"(../../references/workflow/{target})", body)
        checkpoint = (PLUGIN / "references/workflow/manuscript-review.md").read_text()
        self.assertIn("Prose performs one agent-led cohesion inspection", checkpoint)
        self.assertIn("evidence review and investigator promotion", checkpoint)

    def test_inventory_stages_only_the_unified_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "staged"
            result = subprocess.run(
                ["python3", str(ROOT / "scripts/package_inventory.py"), "stage", "cse", str(destination), "--commit", "0" * 40],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            identity = json.loads(result.stdout)
            self.assertEqual(sorted(SKILLS), sorted(identity["payloadSkills"]))
            style = Path("assets/visualize/project/matplotlib/cse.mplstyle")
            self.assertEqual((PLUGIN / style).read_bytes(), (destination / style).read_bytes())
            self.assertFalse((destination / "tests").exists())
            self.assertFalse((destination / "extensions").exists())


if __name__ == "__main__":
    unittest.main()
