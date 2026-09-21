from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugin/scripts/workflow/setup_scientific_project.py"
sys.path.insert(0, str(ROOT / "plugin/scripts/workflow"))
BEGIN = "<!-- CSE:BEGIN PROTOCOL -->"
END = "<!-- CSE:END PROTOCOL -->"
ROLE = "chemical engineer and computational thermodynamics researcher"
DUTIES = "Own the ePC-SAFT parameter decisions and their numerical evidence."
LEGACY_POINTER = "Use the installed CSE skills and read docs/scientific/README.md before route selection."
AGENT_ROLE = "chemical engineer and heat-transfer modeling researcher"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


setup = load_module("setup_scientific_project", SCRIPT)

ADOPTION_POINTER = "Use the source/data adoption recorded in `docs/scientific/CONTEXT.md`."
PRE_FEATURE_PROTOCOL = f"""## CSE Protocol

**Agent role:** Work as {ROLE}.
**Repository role:** analysis.

{DUTIES}

Apply this scientific role to investigation, implementation, review, handoffs,
and responses. Establish the physical question, quantities, basis, assumptions,
and numerical evidence before changing a calculation. Reuse accepted decisions.

Use the installed CSE skills. Read `docs/scientific/README.md` and
`docs/scientific/CONTEXT.md` before selecting the evidence-justified route.

Report the engineering result or capability, supporting evidence, meaning,
and limits before software provenance. Do not invent physical results.

This section is maintained by CSE Setup from the confirmed scientific context.
Revise its inputs through Setup rather than maintaining a separate copy here."""


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, text=True, capture_output=True, check=False)


class ManagedProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()

    def agents(self) -> str:
        return (self.repo / "AGENTS.md").read_text(encoding="utf-8")

    def context(self) -> str:
        return (self.repo / "docs/scientific/CONTEXT.md").read_text(encoding="utf-8")

    def block(self, text: str) -> str:
        self.assertEqual(text.count(BEGIN), 1)
        self.assertEqual(text.count(END), 1)
        return text[text.index(BEGIN):text.index(END) + len(END)]

    def check(self) -> subprocess.CompletedProcess[str]:
        return run("--repo", str(self.repo), "--check-routing", cwd=self.repo)

    def approve(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return run("--repo", str(self.repo), "--reconcile", "--approve", "--role", "analysis", *extra, cwd=self.repo)

    def prepare(self, *extra: str) -> subprocess.CompletedProcess[str]:
        (self.repo / "data").mkdir(exist_ok=True)
        (self.repo / "data/observations.csv").write_text("t_s,T_degC\n0,90\n", encoding="utf-8")
        return run("--repo", str(self.repo), "--role", "tool", "--analysis-id", "cooling-fit",
                   "--input", "data/observations.csv", "--manifest", str(self.repo / ".cse/manifest.json"),
                   *extra, cwd=self.repo)

    def test_setup_generates_cse_pointer_populated_analysis_and_stable_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data" / "observations.csv"
            data.parent.mkdir()
            data.write_text("time_s,temperature_degC\n0,90\n")
            first = root.parent / f"{root.name}-setup-1.json"
            second = root.parent / f"{root.name}-setup-2.json"
            try:
                setup.prepare(root, "cooling-fit", data, first, role="analysis", agent_role_value=AGENT_ROLE)
                configs = [root / ".codex/hooks.json", root / ".claude/settings.json"]
                for config in configs:
                    self.assertFalse(config.exists())
                    config.parent.mkdir()
                    config.write_text("unrelated configuration; Setup must not parse or change it")
                setup.prepare(root, "cooling-fit", data, second, role="analysis")
                for config in configs:
                    self.assertEqual("unrelated configuration; Setup must not parse or change it", config.read_text())
                self.assertEqual(first.read_text(), second.read_text())
                agents = (root / "AGENTS.md").read_text()
                self.assertIn("<!-- CSE:BEGIN PROTOCOL -->", agents)
                self.assertIn(f"**Agent role:** Work as {AGENT_ROLE}.", agents)
                readme = (root / "docs/scientific/README.md").read_text()
                self.assertIn("Research before Design or Build", readme)
                self.assertIn("Diagnose first", readme)
                analysis = root / "analyses/cooling-fit"
                self.assertTrue((analysis / "inputs/observations.csv").is_file())
                self.assertTrue((analysis / "inputs/provenance.json").is_file())
                self.assertFalse((analysis / "notebook.qmd").exists())
                self.assertFalse((analysis / "results").exists())
                self.assertFalse((root / "docs/scientific/adr/templates").exists())
            finally:
                first.unlink(missing_ok=True)
                second.unlink(missing_ok=True)

    def test_setup_requires_explicit_role_and_reconciles_legacy_role(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data.csv"
            data.write_text("x,y\n")
            missing = subprocess.run(
                [sys.executable, str(setup.ROOT / "scripts/workflow/setup_scientific_project.py"),
                 "--repo", str(root), "--analysis-id", "a", "--input", str(data),
                 "--manifest", str(root / "missing.json")],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(2, missing.returncode)
            self.assertFalse((root / "docs/scientific/CONTEXT.md").exists())

            setup.prepare(root, "a", data, root / "manifest.json", role="tool", agent_role_value=AGENT_ROLE)
            context = root / "docs/scientific/CONTEXT.md"
            self.assertEqual("tool", setup.repository_role(context))
            self.assertEqual(1, context.read_text().count("repository role:"))
            before = {
                path.relative_to(root): path.read_bytes()
                for path in root.rglob("*") if path.is_file()
            }
            missing_role = subprocess.run(
                [sys.executable, str(setup.ROOT / "scripts/workflow/setup_scientific_project.py"),
                 "--repo", str(root), "--reconcile", "--approve"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(2, missing_role.returncode)
            self.assertIn("--role is required", missing_role.stderr)
            self.assertEqual(before, {
                path.relative_to(root): path.read_bytes()
                for path in root.rglob("*") if path.is_file()
            })

            for declaration in ("repository role:", "default deliverable:"):
                malformed = f"# Scientific context\n{declaration}\nBasis: molar\n## Heading\n"
                repaired = setup.canonical_context(malformed, "tool")
                self.assertIn("Basis: molar", repaired)
                self.assertIn("## Heading", repaired)
            for multiline in (
                "# Scientific context\nrepository role:\nanalysis\n",
                "# Scientific context\ndefault deliverable:\nresult\n",
            ):
                context.write_text(multiline)
                self.assertIsNone(setup.repository_role(context))
                self.assertIsNone(setup.plan_reconciliation(root)["repository_role"])

            for parent_escape in (False, True):
                escaped = Path(directory) / ("escaped-parent" if parent_escape else "escaped-context")
                escaped.mkdir()
                escaped_data = escaped / "data.csv"
                escaped_data.write_text("x,y\n")
                external = Path(directory) / f"external-{parent_escape}.md"
                external.write_text("# Scientific context\nrepository role: analysis\n")
                if parent_escape:
                    external_root = Path(directory) / "external-root"
                    (external_root / "scientific").mkdir(parents=True)
                    external_context = external_root / "scientific/CONTEXT.md"
                    external_context.write_bytes(external.read_bytes())
                    (escaped / "docs").symlink_to(external_root, target_is_directory=True)
                    external_target = external_context
                else:
                    (escaped / "docs/scientific").mkdir(parents=True)
                    (escaped / "docs/scientific/CONTEXT.md").symlink_to(external)
                    external_target = external
                before_files = {
                    path.relative_to(escaped): path.read_bytes()
                    for path in escaped.rglob("*") if path.is_file() and not path.is_symlink()
                }
                external_before = external_target.read_bytes()
                with self.assertRaises(setup.SetupError):
                    setup.prepare(escaped, "a", escaped_data,
                                  escaped / "manifest.json", role="tool", agent_role_value=AGENT_ROLE)
                self.assertEqual(before_files, {
                    path.relative_to(escaped): path.read_bytes()
                    for path in escaped.rglob("*") if path.is_file() and not path.is_symlink()
                })
                self.assertEqual(external_before, external_target.read_bytes())
                shutil.rmtree(escaped)
                if parent_escape:
                    shutil.rmtree(external_root)
                else:
                    external.unlink()

            for ambiguous in (
                "# Scientific context\nrepository role: report\n",
                "# Scientific context\nrepository role: analysis\nrepository role: tool\n",
                "# Scientific context\nrepository role: analysis\ndefault deliverable: result\n",
            ):
                context.write_text(ambiguous)
                self.assertIsNone(setup.repository_role(context))
                self.assertIsNone(setup.plan_reconciliation(root)["repository_role"])

            context.write_text("# Scientific context\n\ndefault deliverable: capability\n")
            capability_plan = setup.plan_reconciliation(root)
            self.assertEqual("tool", capability_plan["repository_role"])
            self.assertIn("Legacy role proposal: capability", setup.plan_text(capability_plan))
            context.write_text("# Scientific context\n\ndefault deliverable: result\n\nkeep this\n")
            plan = setup.plan_reconciliation(root)
            self.assertEqual("analysis", plan["repository_role"])
            self.assertIn("Legacy role proposal: result", setup.plan_text(plan))
            setup.apply_reconciliation(root, plan, "tool", AGENT_ROLE)
            repaired = context.read_text()
            self.assertEqual("tool", setup.repository_role(context))
            self.assertEqual(1, repaired.count("repository role:"))
            self.assertNotIn("default deliverable:", repaired)
            self.assertIn("keep this", repaired)
            repeat = setup.plan_reconciliation(root)
            setup.apply_reconciliation(root, repeat, "tool", AGENT_ROLE)
            self.assertEqual(repaired, context.read_text())
            self.assertNotIn("Retained source records", repaired)

    def test_setup_previews_and_reconciles_custom_agents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data.csv"
            data.write_text("x,y\n")
            agents = root / "AGENTS.md"
            agents.write_text("# Repository\n\nKeep this guidance.\n\nUse CSE and read docs/scientific/CONTEXT.md.\n")
            before = agents.read_text()
            report = setup.routing_report(root, "analysis", AGENT_ROLE)
            self.assertEqual("insert", report["action"])
            self.assertNotIn("Use CSE and read docs/scientific/CONTEXT.md.", report["proposed"])
            self.assertIn("docs/scientific/README.md", report["proposed"])
            self.assertIn("Keep this guidance.", report["proposed"])
            check = subprocess.run(
                [sys.executable, str(setup.ROOT / "scripts/workflow/setup_scientific_project.py"),
                 "--repo", str(root), "--check-routing"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(1, check.returncode)
            self.assertIn("needs reconciliation", check.stdout)
            self.assertEqual(before, agents.read_text())
            agents.write_text(
                "# Repository\n\nUse CSE and read docs/scientific/CONTEXT.md. "
                "Keep the laboratory safety instructions in this paragraph.\n"
            )
            mixed = setup.routing_report(root, "analysis", AGENT_ROLE)
            self.assertEqual("insert", mixed["action"])
            self.assertIn("Keep the laboratory safety instructions", mixed["proposed"])
            agents.write_text(before)
            collision = root / "docs/scientific/README.md"
            collision.parent.mkdir(parents=True)
            collision.write_text("unrecognized\n")
            with self.assertRaises(setup.SetupError):
                setup.prepare(root, "cooling-fit", data, root / "manifest.json", role="analysis", agent_role_value=AGENT_ROLE)
            self.assertEqual(before, agents.read_text())
            self.assertFalse((root / "docs/scientific/CONTEXT.md").exists())
            collision.unlink()
            manifest_parent = root / "manifest-parent"
            manifest_parent.write_text("not a directory\n")
            with self.assertRaises(setup.SetupError):
                setup.prepare(
                    root, "cooling-fit", data,
                    manifest_parent / "manifest.json",
                    role="analysis", agent_role_value=AGENT_ROLE,
                )
            self.assertEqual(before, agents.read_text())
            self.assertFalse((root / "docs/scientific/CONTEXT.md").exists())
            manifest_parent.unlink()
            setup.prepare(root, "cooling-fit", data, root / "manifest.json", role="analysis", agent_role_value=AGENT_ROLE)
            self.assertIn("Keep this guidance.", agents.read_text())
            self.assertTrue(setup.routing_report(root)["satisfied"])
            self.assertFalse((root / ".codex/hooks.json").exists())
            self.assertFalse((root / ".claude/settings.json").exists())
            check = subprocess.run(
                [sys.executable, str(setup.ROOT / "scripts/workflow/setup_scientific_project.py"),
                 "--repo", str(root), "--check-routing"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(0, check.returncode)
            self.assertIn("Routing: satisfied", check.stdout)

    def test_reconciliation_previews_without_writing_and_merges_root_glossary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            (root / "CONTEXT.md").write_text(
                "# Root glossary\n\n| Term | Meaning | Scope |\n|---|---|---|\n"
                "| certificate | returned proof | engine/* |\n\n"
                "## Avoid\n\n| Avoid | Prefer | Meaning |\n|---|---|---|\n"
                "| proof token | certificate | use the project term |\n"
            )
            (root / "docs").mkdir()
            (root / "docs/caller.md").write_text("See docs/scientific/formulation.tex.\n")
            scientific = root / "docs/scientific"
            scientific.mkdir()
            (scientific / "formulation.tex").write_text("\\section{Formulation}\nRetained equation.\n")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "legacy scientific layout"], cwd=root, check=True)
            before = (root / "CONTEXT.md").read_text()

            plan = setup.plan_reconciliation(root)
            self.assertIn("formulation.tex", setup.plan_text(plan))
            self.assertIn("certificate", plan["merged_context"])
            self.assertFalse((root / "docs/scientific/CONTEXT.md").exists())
            self.assertEqual(before, (root / "CONTEXT.md").read_text())

            setup.apply_reconciliation(root, plan, "analysis", AGENT_ROLE)
            merged = (root / "docs/scientific/CONTEXT.md").read_text()
            lines = merged.splitlines()
            self.assertEqual(1, lines.count("| Term | Meaning | Source | Scope |"))
            self.assertEqual(1, lines.count("|---|---|---|---|"))
            self.assertEqual(1, lines.count("| Avoid | Prefer | Meaning | Scope | Exceptions | Evidence |"))
            self.assertEqual(1, lines.count("|---|---|---|---|---|---|"))
            self.assertIn("| certificate | returned proof | sourceless | engine/* |", merged)
            self.assertIn("| proof token | certificate | use the project term |  |  | sourceless |", merged)
            self.assertIn("repository role: analysis", merged)
            self.assertFalse((root / "CONTEXT.md").exists())
            self.assertFalse((root / "docs/scientific/formulation.tex").exists())
            self.assertTrue((root / "docs/scientific/formulation.md").is_file())
            self.assertIn("docs/scientific/formulation.md", (root / "docs/caller.md").read_text())
            self.assertTrue((root / "docs/scientific/README.md").is_file())
            self.assertFalse((root / ".codex/hooks.json").exists())
            self.assertFalse((root / ".claude/settings.json").exists())

    def legacy_repository(self) -> None:
        (self.repo / "AGENTS.md").write_text(
            f"# My project\n\nKeep the custom build notes.\n\n{LEGACY_POINTER}\n\nCSE execution mode: baton.\n",
            encoding="utf-8",
        )
        scientific = self.repo / "docs/scientific"
        scientific.mkdir(parents=True)
        (scientific / "README.md").write_text("# Scientific project records\n", encoding="utf-8")
        (scientific / "CONTEXT.md").write_text(
            "# Scientific context\n\nrepository role: analysis\n\n## Question and intended use\n\nCooling rate.\n",
            encoding="utf-8",
        )

    def test_fresh_setup_writes_role_first_block_and_repeats_byte_for_byte(self):
        missing = self.prepare()
        self.assertEqual(missing.returncode, 1)
        self.assertIn("agent role is required", missing.stderr)
        self.assertFalse((self.repo / "AGENTS.md").exists())

        result = self.prepare("--agent-role", ROLE, "--responsibilities", DUTIES)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.agents()
        block = self.block(text)
        lines = [line for line in block.splitlines()[1:-1] if line.strip()]
        self.assertEqual(lines[0], "## CSE Protocol")
        self.assertEqual(lines[1], f"**Agent role:** Work as {ROLE}.")
        self.assertEqual(lines[2], "**Repository role:** tool.")
        self.assertIn(DUTIES, block)
        self.assertTrue(text.startswith("# CSE project guidance\n\n" + BEGIN), text[:120])
        self.assertNotIn("MUST use the installed CSE skills", text)
        self.assertIn("CSE execution mode: direct.", text)
        self.assertIn(f"## Agent role\n\nagent role: {ROLE}\n\n{DUTIES}\n", self.context())
        self.assertIn("repository role: tool", self.context())
        self.assertEqual(self.check().returncode, 0)

        before = (text, self.context())
        again = self.prepare()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual((self.agents(), self.context()), before)

    def test_fresh_setup_records_zotero_adoption_and_one_protocol_pointer(self):
        result = self.approve("--agent-role", ROLE, "--responsibilities", DUTIES,
                              "--source-data-adoption", "zotero")
        self.assertEqual(result.returncode, 0, result.stderr)
        context = self.context()
        self.assertIn("source/data adoption: zotero", context)
        self.assertEqual(self.block(self.agents()).count(ADOPTION_POINTER), 1)

    def test_prepare_path_records_project_data_adoption(self):
        result = self.prepare("--agent-role", ROLE, "--responsibilities", DUTIES,
                              "--source-data-adoption", "project-data")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("source/data adoption: project-data", self.context())
        self.assertEqual(self.block(self.agents()).count(ADOPTION_POINTER), 1)

    def test_repeating_source_data_adoption_is_a_byte_for_byte_no_op(self):
        first = self.approve("--agent-role", ROLE, "--responsibilities", DUTIES,
                             "--source-data-adoption", "zotero")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = (self.agents(), self.context())

        again = self.approve("--source-data-adoption", "zotero")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual((self.agents(), self.context()), before)

    def test_source_data_adoption_revision_rewrites_record_and_pointer(self):
        first = self.approve("--agent-role", ROLE, "--responsibilities", DUTIES,
                             "--source-data-adoption", "zotero")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = (self.agents(), self.context())

        revised = self.approve("--source-data-adoption", "project-data")
        self.assertEqual(revised.returncode, 0, revised.stderr)
        self.assertNotEqual((self.agents(), self.context()), before)
        context = self.context()
        self.assertIn("source/data adoption: project-data", context)
        self.assertNotIn("source/data adoption: zotero", context)
        self.assertEqual(self.block(self.agents()).count(ADOPTION_POINTER), 1)

    def test_explicit_none_persists_choice_and_removes_protocol_pointer(self):
        first = self.approve("--agent-role", ROLE, "--responsibilities", DUTIES,
                             "--source-data-adoption", "zotero")
        self.assertEqual(first.returncode, 0, first.stderr)

        cleared = self.approve("--source-data-adoption", "none")
        self.assertEqual(cleared.returncode, 0, cleared.stderr)
        context = self.context()
        self.assertIn("source/data adoption: none", context)
        self.assertNotIn("cse-zotero", context)
        self.assertEqual(self.block(self.agents()).count(ADOPTION_POINTER), 0)

    def test_check_routing_reports_unsupplied_adoption_change(self):
        initial = self.approve("--agent-role", ROLE, "--responsibilities", DUTIES)
        self.assertEqual(initial.returncode, 0, initial.stderr)

        proposed = run("--repo", str(self.repo), "--check-routing", "--role", "analysis",
                       "--source-data-adoption", "zotero", cwd=self.repo)
        self.assertEqual(proposed.returncode, 1)
        self.assertIn("Routing: needs reconciliation", proposed.stdout)

        applied = self.approve("--source-data-adoption", "zotero")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(self.check().returncode, 0)

    def test_unset_source_data_adoption_leaves_existing_block_unchanged(self):
        initial = self.approve("--agent-role", ROLE, "--responsibilities", DUTIES)
        self.assertEqual(initial.returncode, 0, initial.stderr)
        before = (self.agents(), self.context())

        again = self.approve()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual((self.agents(), self.context()), before)
        self.assertNotIn(ADOPTION_POINTER, self.block(self.agents()))
        self.assertNotIn("source/data adoption:", self.context())

    def test_unset_source_data_adoption_preserves_pre_feature_block(self):
        self.legacy_repository()
        context = self.context().replace(
            "## Claim boundaries",
            "## Source/data adoption\n\nsource/data adoption: zotero\n\n## Claim boundaries",
        )
        context += f"\n## Agent role\n\nagent role: {ROLE}\n\n{DUTIES}\n"
        (self.repo / "docs/scientific/CONTEXT.md").write_text(context, encoding="utf-8")
        block = f"{BEGIN}\n{PRE_FEATURE_PROTOCOL}\n{END}"
        (self.repo / "AGENTS.md").write_text(f"# My project\n\n{block}\n", encoding="utf-8")
        before = (self.agents(), self.context())

        again = self.approve()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual((self.agents(), self.context()), before)

    def test_pointer_only_repository_is_diagnosed_then_upgraded_preserving_guidance(self):
        self.legacy_repository()
        check = self.check()
        self.assertEqual(check.returncode, 1)
        self.assertIn("Managed CSE Protocol block: missing; agent role: missing", check.stdout)

        refused = self.approve()
        self.assertEqual(refused.returncode, 1)
        self.assertIn("agent role is required", refused.stderr)
        self.assertIn(LEGACY_POINTER, self.agents())

        applied = self.approve("--agent-role", ROLE)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        text = self.agents()
        block = self.block(text)
        self.assertTrue(text.startswith("# My project\n\n" + BEGIN), text[:120])
        self.assertIn("Keep the custom build notes.", text)
        self.assertIn("CSE execution mode: baton.", text)
        self.assertNotIn(LEGACY_POINTER, text)
        self.assertIn("**Repository role:** analysis.", block)
        self.assertIn(f"agent role: {ROLE}", self.context())
        self.assertIn("Cooling rate.", self.context())
        self.assertEqual(self.check().returncode, 0)

        before = (text, self.context())
        again = self.approve()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual((self.agents(), self.context()), before)

    def test_role_change_manual_drift_and_malformed_markers(self):
        self.legacy_repository()
        self.assertEqual(self.approve("--agent-role", ROLE).returncode, 0)

        changed = self.approve("--agent-role", "heat-transfer modeling researcher",
                               "--responsibilities", "Own the cooling model.")
        self.assertEqual(changed.returncode, 0, changed.stderr)
        text = self.agents()
        self.assertIn("**Agent role:** Work as heat-transfer modeling researcher.", text)
        self.assertNotIn(ROLE, text)
        self.assertNotIn(ROLE, self.context())
        self.assertIn("Own the cooling model.", self.context())
        self.assertIn("Own the cooling model.", self.block(text))

        (self.repo / "AGENTS.md").write_text(text.replace("Work as heat-transfer", "Work as a manually edited"), encoding="utf-8")
        drift = self.check()
        self.assertEqual(drift.returncode, 1)
        self.assertIn("Managed CSE Protocol block: stale", drift.stdout)
        self.assertIn("-**Agent role:** Work as a manually edited", drift.stdout)
        self.assertIn("+**Agent role:** Work as heat-transfer", drift.stdout)
        repaired = self.approve()
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        self.assertEqual(self.agents(), text)

        broken = text + "\n" + BEGIN + "\n"
        (self.repo / "AGENTS.md").write_text(broken, encoding="utf-8")
        self.assertIn("malformed", self.check().stdout)
        refused = self.approve()
        self.assertEqual(refused.returncode, 1)
        self.assertIn("unmatched", refused.stderr)
        self.assertEqual(self.agents(), broken)


if __name__ == "__main__":
    unittest.main()
