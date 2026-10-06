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
ROUTES = "\n".join(f"- {line.strip()}" for line in (ROOT / "plugin/assets/workflow/skill-routing.txt").read_text(encoding="utf-8").splitlines() if line.strip())
PRE_FEATURE_PROTOCOL = f"""## CSE Protocol

**Agent role:** Work as {ROLE}.
**Repository role:** analysis.

{DUTIES}

Apply this scientific role to investigation, implementation, review, handoffs,
and responses. Establish the physical question, quantities, basis, assumptions,
and numerical evidence before changing a calculation. Reuse accepted decisions.

Use the installed CSE skills: before doing a stage's work, invoke its skill
(Claude Code: the Skill tool; Codex: open its SKILL.md). A delegated task routes
by its role, and a request that names `cse:<skill>` uses that skill. Read
`docs/scientific/README.md` and `docs/scientific/CONTEXT.md` before selecting the
evidence-justified route.

{ROUTES}

For a requested retrospective, invoke `cse:audit` and use its retrospective reference.

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
                "# Root glossary\n\n## Glossary\n\n| Term | Meaning | Scope |\n|---|---|---|\n"
                "| certificate | returned proof | engine/* |\n\n"
                "## Avoid\n\n| Avoid | Prefer | Meaning |\n|---|---|---|\n"
                "| proof token | certificate | use the project term |\n"
            )
            (root / "docs").mkdir()
            (root / "docs/caller.md").write_text("See docs/scientific/formulation.tex.\n")
            scientific = root / "docs/scientific"
            scientific.mkdir()
            (scientific / "formulation.tex").write_text("\\section{Formulation}\nRetained equation.\n")
            (scientific / "formulation.md").write_text("# Existing formulation\nExisting note.\n")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "legacy scientific layout"], cwd=root, check=True)
            before = (root / "CONTEXT.md").read_text()

            plan = setup.plan_reconciliation(root)
            self.assertIn("formulation.tex", setup.plan_text(plan))
            self.assertIn("certificate", plan["merged_glossary"])
            self.assertFalse((root / "docs/scientific/CONTEXT.md").exists())
            self.assertEqual(before, (root / "CONTEXT.md").read_text())

            setup.apply_reconciliation(root, plan, "analysis", AGENT_ROLE)
            merged = (root / "docs/scientific/CONTEXT.md").read_text()
            self.assertNotIn("| Term |", merged)
            self.assertNotIn("## Avoid", merged)
            glossary = (root / "GLOSSARY.md").read_text()
            self.assertIn("**certificate**:\nreturned proof\nSource: sourceless\nScope: `engine/*`", glossary)
            self.assertIn("## Prose avoid rules", merged)
            self.assertIn("| proof token | certificate | use the project term |", merged)
            self.assertIn("repository role: analysis", merged)
            self.assertFalse((root / "CONTEXT.md").exists())
            self.assertFalse((root / "docs/scientific/formulation.tex").exists())
            self.assertTrue((root / "docs/scientific/formulation.md").is_file())
            formulation = (root / "docs/scientific/formulation.md").read_text()
            self.assertIn("Existing note.", formulation)
            self.assertIn("# Formulation", formulation)
            self.assertIn("Retained equation.", formulation)
            self.assertIn("docs/scientific/formulation.md", (root / "docs/caller.md").read_text())
            self.assertTrue((root / "docs/scientific/README.md").is_file())
            self.assertFalse((root / ".codex/hooks.json").exists())
            self.assertFalse((root / ".claude/settings.json").exists())

    def test_reconciliation_migrates_context_tables_to_root_glossary(self):
        root = self.repo
        scientific = root / "docs/scientific"
        scientific.mkdir(parents=True)
        (scientific / "CONTEXT.md").write_text(
            f"# Scientific context\n\nrepository role: analysis\n\n## Agent role\n\nagent role: {ROLE}\n\n{DUTIES}\n\n"
            "## Question\n\nCooling rate.\n\n## Owners\n\nRetain the investigator.\n\n"
            "## Source/data adoption\n\nsource/data adoption: zotero\n\n"
            "## Glossary\n\n| Term | Meaning | Source | Scope |\n|---|---|---|---|\n"
            "| certificate | returned proof | paper §2 | engine/* |\n\n"
            "## Avoid\n\n| Avoid | Prefer | Meaning | Scope | Exceptions | Evidence |\n"
            "|---|---|---|---|---|---|\n| proof token | certificate | returned proof | engine/* | | paper §2 |\n"
        )
        (root / "CONTEXT.md").write_text(
            "# Old vocabulary\n\n## Glossary\n\n| Term | Meaning | Scope |\n|---|---|---|\n"
            "| certificate | duplicate definition | engine/* |\n| flux | transported heat | analyses/* |\n\n"
            "## Owners\n\nRetain the source owner.\n"
        )
        (root / "notes").mkdir()
        (root / "notes/CONTEXT.md").write_text(
            "# Nested vocabulary\n\n## Avoid\n\n| Avoid | Prefer | Meaning |\n|---|---|---|\n"
            "| heat rate | flux | transported heat |\n\n## Question\n\nRetain the nested question.\n"
        )
        (root / "caller.md").write_text("See notes/CONTEXT.md.\n")
        before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
        preview = run("--repo", str(root), "--reconcile", "--role", "analysis", cwd=root)
        self.assertEqual(0, preview.returncode, preview.stderr)
        self.assertIn("GLOSSARY.md", preview.stdout)
        self.assertEqual(before, {path: path.read_bytes() for path in root.rglob("*") if path.is_file()})
        applied = self.approve("--agent-role", ROLE)
        self.assertEqual(0, applied.returncode, applied.stderr)
        glossary = (root / "GLOSSARY.md").read_text()
        self.assertTrue(glossary.startswith("# "))
        self.assertIn("\n## Language\n", glossary)
        self.assertIn("**certificate**:\nreturned proof\n_Avoid_: proof token\nSource: paper §2\nScope: `engine/*`", glossary)
        self.assertIn("**flux**:\ntransported heat\nSource: sourceless\nScope: `analyses/*`", glossary)
        self.assertEqual(1, glossary.count("**certificate**:"))
        context = self.context()
        self.assertNotIn("## Glossary", context)
        self.assertNotIn("## Avoid", context)
        self.assertNotIn("| Term |", context)
        self.assertIn("## Prose avoid rules", context)
        self.assertIn("| heat rate | flux | transported heat |", context)
        self.assertIn("[GLOSSARY.md](../../GLOSSARY.md)", context)
        self.assertIn("Cooling rate.", context)
        self.assertIn("Retain the investigator.", context)
        self.assertEqual(1, context.count("agent role:"))
        self.assertIn(f"agent role: {ROLE}", context)
        self.assertIn(DUTIES, context)
        self.assertIn("source/data adoption: zotero", context)
        self.assertNotIn("Retain the source owner.", context)
        self.assertIn("Retain the nested question.", context)
        self.assertTrue((root / "CONTEXT.md").exists())  # The conflicting duplicate stays in place.
        self.assertIn("duplicate definition", (root / "CONTEXT.md").read_text())
        self.assertFalse((root / "notes/CONTEXT.md").exists())
        self.assertEqual("See docs/scientific/CONTEXT.md.\n", (root / "caller.md").read_text())
        stray = root / "CONTEXT.md"
        stray.write_text(stray.read_text().replace("Retain the source owner.", "Edited source owner."))
        setup.apply_reconciliation(root, setup.plan_reconciliation(root, "analysis"), "analysis", ROLE)
        self.assertEqual(context, self.context())
        self.assertIn("Edited source owner.", stray.read_text())

    def test_reconciliation_preserves_existing_glossary_and_adds_only_missing_terms(self):
        root = self.repo
        original = "# Heat transfer\n\n## Language\n\n**Flux**:\nExisting definition.\n_Avoid_: heat flow\nSource: paper §1\nScope: engine/*\n\n\n"
        (root / "GLOSSARY.md").write_text(original)
        (root / "CONTEXT.md").write_text(
            "# Old vocabulary\n\n## Glossary\n\n| Term | Meaning | Source | Scope |\n|---|---|---|---|\n"
            "| flux | replacement must not win | paper §2 | other/* |\n"
            "| gradient | spatial derivative | paper §3 | engine/* |\n"
            "| gradient | duplicate | paper §3 | engine/* |\n"
        )
        plan = setup.plan_reconciliation(root, "analysis")
        self.assertEqual(original, (root / "GLOSSARY.md").read_text())
        setup.apply_reconciliation(root, plan, "analysis", ROLE)
        glossary = (root / "GLOSSARY.md").read_text()
        self.assertTrue(glossary.startswith(original))
        self.assertNotIn("replacement must not win", glossary)
        self.assertEqual(1, glossary.count("**gradient**:"))
        self.assertIn("Source: paper §3", glossary)
        repeat = setup.plan_reconciliation(root, "analysis")
        setup.apply_reconciliation(root, repeat, "analysis", ROLE)
        self.assertEqual(glossary, (root / "GLOSSARY.md").read_text())
        self.assertFalse((root / "GLOSSARY-MAP.md").exists())

    def test_reconciliation_reads_every_mapped_glossary_without_creating_a_map(self):
        root = self.repo
        mapping = "# Glossary Map\n\n## Contexts\n\n- [Engine](./src/engine/GLOSSARY.md): calculations\n- [Study](./analyses/GLOSSARY.md): evidence\n"
        (root / "GLOSSARY-MAP.md").write_text(mapping)
        for directory, term in (("src/engine", "certificate"), ("analyses", "flux")):
            path = root / directory / "GLOSSARY.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"# Scientific vocabulary\n\n## Language\n\n**{term}**:\nA project quantity.\n_Avoid_: old name\nSource: sourceless\n")
        before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
        plan = setup.plan_reconciliation(root, "analysis")
        self.assertEqual({"src/engine/GLOSSARY.md", "analyses/GLOSSARY.md"}, set(plan.get("glossaries", [])))
        self.assertIn("certificate", plan["sourceless_terms"])
        self.assertIn("flux", plan["sourceless_terms"])
        setup.apply_reconciliation(root, plan, "analysis", ROLE)
        self.assertEqual(before, {path: path.read_bytes() for path in before})
        self.assertFalse((root / "GLOSSARY.md").exists())
        (root / "GLOSSARY-MAP.md").unlink()
        setup.apply_reconciliation(root, setup.plan_reconciliation(root, "analysis"), "analysis", ROLE)
        self.assertFalse((root / "GLOSSARY-MAP.md").exists())

    def test_reconciliation_preserves_lossless_rows_and_prose_rule_columns(self):
        root = self.repo
        scientific = root / "docs/scientific"
        scientific.mkdir(parents=True)
        original = "# Heat\n\n## Language\n\n**flux**:\nHeat rate per area.\nSource: paper §1\nScope: `engine/*`"
        (root / "GLOSSARY.md").write_text(original)
        (root / "src/data").mkdir(parents=True)
        (root / "src/data/GLOSSARY.md").write_text("# Data\n\n## Language\n\n**division**:\nA partition group.\nSource: paper §4")
        (root / "GLOSSARY-MAP.md").write_text("# Glossary Map\n\n## Contexts\n\n- [Data](./src/data/GLOSSARY.md): retained data\n")
        (scientific / "CONTEXT.md").write_text(
            "# Scientific context\n\nrepository role: analysis\n\n## Glossary\n\n"
            "| Term | Meaning | Source | Scope |\n|---|---|---|---|\n"
            "| escaped | a \\| b | paper §2 | analyses/* |\n"
            "| spectral | Source: power density of the source. | paper §6 | analyses/* |\n\n"
            "| Term | Meaning | Units |\n|---|---|---|\n| area | surface area | m² |\n\n"
            "## Avoid\n\n| Avoid | Prefer | Meaning | Scope | Exceptions | Evidence |\n|---|---|---|---|---|---|\n"
            "| heat flow | flux | Heat rate per area. | engine/* | | paper §1 |\n"
            "| parcel | division | A partition group. | src/data/* | | paper §4 |\n"
            "| heat token | flux | Prefer the scientific name. | manuscripts/* | heat token identifier | user correction |\n\n"
            "## Nomenclature\n\n| Term | Meaning | Units |\n|---|---|---|\n| length | distance | m |\n\n"
            "```markdown\n## Glossary\n\n| Term | Meaning | Source |\n|---|---|---|\n| sample | example only | paper §5 |\n```\n"
        )
        plan = setup.plan_reconciliation(root, "analysis")
        preview = setup.plan_text(plan)
        self.assertIn("`docs/scientific/CONTEXT.md`: | length | distance | m | — not a Glossary or Avoid table", preview)
        self.assertIn("Units", preview)
        self.assertIn("heat token", preview)
        self.assertIn("definition starts with a glossary metadata label", preview)
        setup.apply_reconciliation(root, plan, "analysis", ROLE)
        glossary = (root / "GLOSSARY.md").read_text()
        self.assertIn("**escaped**:\na | b\nSource: paper §2\nScope: `analyses/*`", glossary)
        self.assertIn("_Avoid_: heat flow", glossary)
        self.assertIn("_Avoid_: parcel", (root / "src/data/GLOSSARY.md").read_text())
        self.assertNotIn("_Avoid_: heat token", glossary)
        self.assertNotIn("_Avoid_: \n", glossary)
        context = self.context()
        self.assertIn("| area | surface area | m² |", context)
        self.assertIn("| spectral | Source: power density of the source. | paper §6 | analyses/* |", context)
        self.assertNotIn("**spectral**", glossary)
        self.assertIn("| length | distance | m |", context)
        self.assertIn("```markdown\n## Glossary\n\n| Term | Meaning | Source |", context)
        self.assertNotIn("**sample**:", glossary)
        self.assertIn("## Prose avoid rules", context)
        self.assertIn("| heat token | flux | Prefer the scientific name. | manuscripts/* | heat token identifier | user correction |", context)
        (root / "manuscripts").mkdir()
        prose = root / "manuscripts/report.md"
        prose.write_text("The heat token identifier is fixed.\n")
        checker = ROOT / "plugin/scripts/workflow/check_prose.py"
        accepted = subprocess.run([sys.executable, str(checker), "--root", str(root), str(prose)], text=True, capture_output=True)
        self.assertEqual(0, accepted.returncode, accepted.stdout + accepted.stderr)
        prose.write_text("The heat token changed.\n")
        rejected = subprocess.run([sys.executable, str(checker), "--root", str(root), str(prose)], text=True, capture_output=True)
        self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)
        self.assertIn("heat token", rejected.stdout)
        (root / "engine").mkdir()
        outside_scope = root / "engine/report.md"
        outside_scope.write_text("The heat token changed.\n")
        accepted = subprocess.run([sys.executable, str(checker), "--root", str(root), str(outside_scope)], text=True, capture_output=True)
        self.assertEqual(0, accepted.returncode, accepted.stdout + accepted.stderr)

    def test_glossary_additions_stay_inside_language_before_later_sections(self):
        root = self.repo
        (root / "GLOSSARY.md").write_text("# Heat\n\n## Language\n\n**flux**:\nHeat rate.\nSource: paper §1\n\n## Relationships\n\nKeep this relationship.\n")
        (root / "CONTEXT.md").write_text("# Scientific context\n\n## Glossary\n\n| Term | Meaning | Source | Scope |\n|---|---|---|---|\n| schema | Scientific classification. | paper §2 | analyses/* |\n")
        setup.apply_reconciliation(root, setup.plan_reconciliation(root, "analysis"), "analysis", ROLE)
        first = (root / "GLOSSARY.md").read_text()
        self.assertLess(first.index("**schema**:"), first.index("## Relationships"))
        (root / "CONTEXT.md").write_text("# Old terms\n\n## Glossary\n\n| Term | Meaning | Source | Scope |\n|---|---|---|---|\n| schema | Scientific classification. | paper §2 | analyses/* |\n")
        setup.apply_reconciliation(root, setup.plan_reconciliation(root, "analysis"), "analysis", ROLE)
        self.assertEqual(first, (root / "GLOSSARY.md").read_text())
        self.assertEqual(1, first.count("**schema**:"))
        (root / "analyses").mkdir()
        (root / "analyses/report.md").write_text("The schema is fixed.\n")
        result = subprocess.run([sys.executable, str(ROOT / "plugin/scripts/workflow/check_prose.py"), "--root", str(root), str(root / "analyses/report.md")], text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_matt_context_and_map_are_preview_only_and_byte_identical(self):
        root = self.repo
        old = "# Heat\n\n## Language\n\n**flux**:\nHeat rate.\n_Avoid_: heat flow\n\n## Relationships\n\nRetain this relationship.\n"
        (root / "CONTEXT.md").write_text(old)
        (root / "CONTEXT-MAP.md").write_text("# Context Map\n\n## Contexts\n\n- [Heat](./src/heat/CONTEXT.md): heat transfer\n- [Mass](./src/mass/CONTEXT.md): mass transfer\n")
        for name in ("heat", "mass"):
            path = root / "src" / name
            path.mkdir(parents=True)
            (path / "CONTEXT.md").write_text(old.replace("flux", f"{name} flux"))
            (path / "README.md").write_text("[terms](./CONTEXT.md)\n")
        (root / "src/empty").mkdir()
        (root / "src/empty/CONTEXT.md").write_text("# Empty\n\n## Language\n\n## Relationships\n\nKeep this.\n")
        (root / "caller.md").write_text("[terms](./CONTEXT.md) and [map](./CONTEXT-MAP.md).\n")
        before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
        for existing in (False, True):
            if existing:
                (root / "GLOSSARY.md").write_text("# Existing vocabulary\n\n## Language\n")
                (root / "GLOSSARY-MAP.md").write_text("# Glossary Map\n\n## Contexts\n\n- [Heat](./src/heat/GLOSSARY.md): lazy glossary\n")
                before.update({root / name: (root / name).read_bytes() for name in ("GLOSSARY.md", "GLOSSARY-MAP.md")})
            plan = setup.plan_reconciliation(root, "analysis")
            preview = setup.plan_text(plan)
            self.assertIn("Matt Pocock's skills 1.3 read `GLOSSARY.md`", preview)
            self.assertIn("git mv CONTEXT.md GLOSSARY.md", preview)
            self.assertIn("git mv src/heat/CONTEXT.md src/heat/GLOSSARY.md", preview)
            self.assertIn("git mv src/empty/CONTEXT.md src/empty/GLOSSARY.md", preview)
            self.assertIn("git mv CONTEXT-MAP.md GLOSSARY-MAP.md", preview)
            self.assertEqual(before, {path: path.read_bytes() for path in before})
            setup.apply_reconciliation(root, plan, "analysis", ROLE)
            self.assertEqual(before, {path: path.read_bytes() for path in before})
            self.assertNotIn("Retain this relationship.", self.context())
            self.assertIn("`CONTEXT.md` owns the question", (root / "docs/scientific/README.md").read_text())
            if not existing:
                self.assertFalse((root / "GLOSSARY.md").exists())
                self.assertFalse((root / "GLOSSARY-MAP.md").exists())

    def test_later_avoid_rows_use_the_existing_prose_section(self):
        root = self.repo
        for word in ("first", "second"):
            (root / "CONTEXT.md").write_text(
                "# Scientific context\n\n## Avoid\n\n| Avoid | Prefer | Meaning | Scope | Exceptions | Evidence |\n"
                f"|---|---|---|---|---|---|\n| {word} token | flux | Heat rate. | reports/* | | paper §1 |\n"
            )
            setup.apply_reconciliation(root, setup.plan_reconciliation(root, "analysis"), "analysis", ROLE)
            if word == "first":
                context = root / "docs/scientific/CONTEXT.md"
                context.write_text(context.read_text() + "\n## Numerical limits\n\nRetain this bound.\n")
        context = self.context()
        self.assertEqual(1, context.count("## Prose avoid rules"))
        self.assertIn("| first token | flux |", context)
        self.assertLess(context.index("| second token | flux |"), context.index("## Numerical limits"))
        for name, ending in (("a", ""), ("b", "\n")):
            (root / "notes" / name).mkdir(parents=True)
            (root / "notes" / name / "CONTEXT.md").write_text(
                "# Notes\n\n## Avoid\n\n| Avoid | Prefer | Meaning | Scope | Exceptions | Evidence |\n"
                f"|---|---|---|---|---|---|\n| {name} token | flux | Heat rate. | notes/* | | paper §1 |{ending}")
        setup.apply_reconciliation(root, setup.plan_reconciliation(root, "analysis"), "analysis", ROLE)
        rows = [line for line in self.context().splitlines() if "| a token |" in line or "| b token |" in line]
        self.assertEqual(2, len(rows), rows)

    def test_reconciliation_moves_nested_latex_document_trees_together(self):
        root = self.repo
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        (root / "AGENTS.md").write_text("# Project\n\nKeep this note.\n")
        scientific = root / "docs/scientific"
        scientific.mkdir(parents=True)
        (scientific / "README.md").write_text("# Scientific records\n")
        (scientific / "CONTEXT.md").write_text(
            "# Scientific context\n\nrepository role: analysis\n\n## Question and intended use\n\nStudy.\n"
        )

        document = scientific / "cooling/manuscript"
        (document / "figures").mkdir(parents=True)
        (document / "scripts").mkdir()
        (document / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Result.\\end{document}\n")
        (document / "figures/x.pdf").write_bytes(b"%PDF-1.4 retained figure\n")
        (document / "scripts/y.py").write_text("print('retained analysis')\n")
        (document / "CONTEXT.md").write_text("# Manuscript context\n\nRetain this research note.\n")

        classed = scientific / "methods/source"
        (classed / "styles").mkdir(parents=True)
        (classed / "article.tex").write_text("\\documentclass{article}\n\\begin{document}Methods.\\end{document}\n")
        (classed / "styles/paper.sty").write_text("\\ProvidesPackage{paper}\n")
        duplicate = b'{"rate": 1}\n'
        (document / "params.json").write_bytes(duplicate)
        canonical = scientific / "latex/cooling/manuscript"
        canonical.mkdir(parents=True)
        (canonical / "params.json").write_bytes(duplicate)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)

        plan = setup.plan_reconciliation(root, role="analysis")
        expected = {
            "docs/scientific/cooling/manuscript/main.tex": "docs/scientific/latex/cooling/manuscript/main.tex",
            "docs/scientific/cooling/manuscript/figures/x.pdf": "docs/scientific/latex/cooling/manuscript/figures/x.pdf",
            "docs/scientific/cooling/manuscript/scripts/y.py": "docs/scientific/latex/cooling/manuscript/scripts/y.py",
            "docs/scientific/methods/source/article.tex": "docs/scientific/latex/methods/source/article.tex",
            "docs/scientific/methods/source/styles/paper.sty": "docs/scientific/latex/methods/source/styles/paper.sty",
        }
        planned = {item["source"]: item["target"] for item in plan["moves"] if item["source"] in expected}
        self.assertEqual(expected, planned)
        self.assertIn("docs/scientific/latex/cooling/manuscript/figures/x.pdf", setup.plan_text(plan))
        self.assertTrue((document / "figures/x.pdf").is_file())

        setup.apply_reconciliation(root, plan, "analysis", AGENT_ROLE)
        for source, target in expected.items():
            self.assertFalse((root / source).exists(), source)
            self.assertTrue((root / target).is_file(), target)
        self.assertEqual(b"%PDF-1.4 retained figure\n",
                         (root / "docs/scientific/latex/cooling/manuscript/figures/x.pdf").read_bytes())
        self.assertEqual("print('retained analysis')\n",
                         (root / "docs/scientific/latex/cooling/manuscript/scripts/y.py").read_text())
        self.assertFalse((document / "params.json").exists())
        self.assertEqual(duplicate, (canonical / "params.json").read_bytes())
        self.assertIn("Retain this research note.", (scientific / "CONTEXT.md").read_text())
        self.assertFalse((root / "docs/scientific/latex/cooling/manuscript/CONTEXT.md").exists())

    def test_reconciliation_refuses_differing_document_companion_before_writes(self):
        root = self.repo
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        (root / "AGENTS.md").write_text("# Project\n\nKeep this note.\n")
        scientific = root / "docs/scientific"
        (scientific / "study/figures").mkdir(parents=True)
        (scientific / "study/scripts").mkdir()
        (scientific / "README.md").write_text("# Scientific records\n")
        (scientific / "CONTEXT.md").write_text(
            "# Scientific context\n\nrepository role: analysis\n\n## Question and intended use\n\nStudy.\n"
        )
        (scientific / "study/main.tex").write_text("\\documentclass{article}\n")
        (scientific / "study/figures/x.pdf").write_bytes(b"%PDF-1.4 retained figure\n")
        (scientific / "study/scripts/y.py").write_text("print('retained analysis')\n")
        (scientific / "study/params.json").write_text('{"rate": 2}\n')
        target = scientific / "latex/study/params.json"
        target.parent.mkdir(parents=True)
        target.write_text('{"rate": 1}\n')
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)

        plan = setup.plan_reconciliation(root, role="analysis")
        names = (
            "AGENTS.md", "docs/scientific/README.md", "docs/scientific/CONTEXT.md",
            "docs/scientific/study/main.tex", "docs/scientific/study/figures/x.pdf",
            "docs/scientific/study/scripts/y.py", "docs/scientific/study/params.json",
            "docs/scientific/latex/study/params.json",
        )
        before = {name: (root / name).read_bytes() for name in names}
        status = subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True,
                                capture_output=True, text=True).stdout

        with self.assertRaisesRegex(setup.SetupError, "manual merge required"):
            setup.apply_reconciliation(root, plan, "analysis", AGENT_ROLE)

        self.assertEqual(before, {name: (root / name).read_bytes() for name in names})
        after_status = subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True,
                                      capture_output=True, text=True).stdout
        self.assertEqual(status, after_status)

    def legacy_repository(self) -> None:
        (self.repo / "AGENTS.md").write_text(
            f"# My project\n\nKeep the custom build notes.\n\n{LEGACY_POINTER}\n\nKeep this project-specific note.\n",
            encoding="utf-8",
        )
        scientific = self.repo / "docs/scientific"
        scientific.mkdir(parents=True)
        (scientific / "README.md").write_text("# Scientific project records\n", encoding="utf-8")
        (scientific / "CONTEXT.md").write_text(
            "# Scientific context\n\nrepository role: analysis\n\n"
            "Project vocabulary: [GLOSSARY.md](../../GLOSSARY.md).\n\n"
            "## Question and intended use\n\nCooling rate.\n",
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
        self.assertIn("Keep this project-specific note.", text)
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
