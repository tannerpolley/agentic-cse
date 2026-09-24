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
    "setup", "research", "diagnose", "design", "build", "analyze", "summarize",
    "review", "write", "prose", "workflow", "audit", "zotero", "mathpix", "data", "digitize",
    "plot", "tikz", "pgfplots", "latex", "quarto", "beamer",
}


class PluginBehaviorTests(unittest.TestCase):
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
            "summarize": "Execute and deliver", "write": "Execute and deliver",
        }
        for skill, phase in phase_descriptions.items():
            interface = yaml.safe_load((PLUGIN / "skills" / skill / "agents/openai.yaml").read_text())["interface"]
            self.assertNotIn("Workflow", interface["display_name"])
            self.assertIn(phase.replace(" or ", " / "), interface["display_name"])
        prose = yaml.safe_load((PLUGIN / "skills/prose/SKILL.md").read_text().split("---", 2)[1])
        self.assertEqual("supporting", prose["metadata"]["cse-kind"])
        workflow = (PLUGIN / "skills/workflow/SKILL.md").read_text()
        normalized_workflow = " ".join(workflow.split())
        for phrase in (
            "CSE owns its scientific stages, evidence, and acceptance",
            "selected by project preference or explicit task override",
            "does not require a Build worker",
        ):
            self.assertIn(phrase, normalized_workflow)
        frontmatter = yaml.safe_load(workflow.split("---", 2)[1])
        self.assertEqual({"github-and-git"}, set(frontmatter["metadata"]["cse-routing"]["conditional"]))
        build = yaml.safe_load((PLUGIN / "skills/build/SKILL.md").read_text().split("---", 2)[1])
        self.assertIn("cse-pi-worker", build["metadata"]["cse-routing"]["conditional"])
        for skill in ("diagnose", "analyze", "review", "workflow"):
            metadata = yaml.safe_load((PLUGIN / "skills" / skill / "SKILL.md").read_text().split("---", 2)[1])
            self.assertNotIn("cse-pi-worker", metadata["metadata"]["cse-routing"]["conditional"])
        self.assertNotIn("wait_threads", workflow)
        self.assertNotIn("send_message_to_thread", workflow)
        self.assertFalse((PLUGIN / "references/workflow/execution-modes.md").exists())
        setup = (PLUGIN / "skills/setup/SKILL.md").read_text()
        self.assertIn("CSE execution mode: direct.", setup)
        self.assertIn("CSE execution mode: baton.", setup)
        projects = (PLUGIN / "references/workflow/scientific-projects.md").read_text()
        self.assertIn("required renderer executable", projects)
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
        profiles = (PLUGIN / "references/visualize/latex-article-profiles.md").read_text()
        self.assertIn("`cse:prose`", profiles)
        self.assertNotIn("core Review's manuscript", profiles)
        self.assertIn("evidence review and investigator promotion", profiles)

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
            self.assertFalse((destination / "tests").exists())
            self.assertFalse((destination / "extensions").exists())


if __name__ == "__main__":
    unittest.main()
