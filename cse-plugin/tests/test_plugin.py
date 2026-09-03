from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = {"setup", "research", "diagnose", "design", "build", "analyze", "review", "summarize", "write"}
SUPPORTING = {"audit"}
CORE = WORKFLOW | SUPPORTING
SOURCES = {"zotero", "mathpix", "data", "digitize"}
VISUALIZE = {"plot", "tikz", "pgfplots", "latex", "quarto", "beamer"}
SKILLS = CORE | SOURCES | VISUALIZE
SOURCES_ROOT = ROOT / "extensions/cse-sources"
VISUALIZE_ROOT = ROOT / "extensions/cse-visualize"
WORKFLOW_ORDERS = {
    "setup": "01", "research": "02A", "diagnose": "02B", "design": "03",
    "build": "04", "analyze": "05", "summarize": "06", "review": "07",
    "write": "08",
}
ROUTE_PATHS = {
    **{path.stem: f"references/{path.name}" for path in (ROOT / "references").glob("*.md")},
    "terminology": "references/terminology.md",
    "BANNED": "BANNED.md",
}
DURABLE_PROSE_SKILLS = WORKFLOW


def skill_root(name: str) -> Path:
    return SOURCES_ROOT if name in SOURCES else VISUALIZE_ROOT if name in VISUALIZE else ROOT


def route_paths(name: str) -> dict[str, str]:
    root = skill_root(name)
    paths = {path.stem: f"references/{path.name}" for path in (root / "references").glob("*.md")}
    if root == ROOT:
        paths.update({"terminology": "references/terminology.md", "BANNED": "BANNED.md"})
    return paths


def skill_frontmatter(name: str) -> dict:
    text = (skill_root(name) / "skills" / name / "SKILL.md").read_text()
    return yaml.safe_load(text.split("---", 2)[1])


def skill_text(name: str) -> str:
    return (skill_root(name) / "skills" / name / "SKILL.md").read_text()


def projected_documents(route: list[str]) -> list[str]:
    """Project the declared direct-entry reads in deterministic order."""
    documents: list[str] = []
    for name in route:
        routing = skill_frontmatter(name)["metadata"]["cse-routing"]
        documents.append(f"skills/{name}/SKILL.md")
        documents.extend(ROUTE_PATHS[reference] for reference in routing["direct"])
    return documents


def effective_projected_documents(route: list[str]) -> list[str]:
    """Reuse each unchanged document after the first internal-handoff read."""
    documents: list[str] = []
    seen: set[str] = set()
    for document in projected_documents(route):
        if document not in seen:
            seen.add(document)
            documents.append(document)
    return documents


def routing_analysis() -> dict:
    direct = {
        name: skill_frontmatter(name)["metadata"]["cse-routing"]["direct"]
        for name in sorted(SKILLS)
    }
    conditional = {
        name: skill_frontmatter(name)["metadata"]["cse-routing"]["conditional"]
        for name in sorted(SKILLS)
    }
    direct_counts = Counter(reference for values in direct.values() for reference in values)
    trigger_report = {
        name: {
            reference: bool(re.search(
                rf"(?i)(?:activate|when|for|selected|scope|conditional).{{0,180}}{re.escape(reference)}",
                skill_text(name),
            ))
            for reference in values
        }
        for name, values in conditional.items()
    }
    exact_assertions = []
    for line_number, line in enumerate((ROOT / "tests/test_plugin.py").read_text().splitlines(), 1):
        if re.search(r"self\.assert(?:In|NotIn)\(", line) and re.search(r"['\"]", line):
            exact_assertions.append({"line": line_number, "text": line.strip()})

    routes = {
        "research": ["research", "design", "build", "analyze", "summarize", "review"],
        "diagnose": ["diagnose", "research", "design", "build", "analyze", "summarize", "review"],
    }
    projected = {}
    for route_name, route in routes.items():
        declared_documents = projected_documents(route)
        declared_counts = Counter(declared_documents)
        effective_documents = effective_projected_documents(route)
        effective_counts = Counter(effective_documents)
        projected[route_name] = {
            "route": route,
            "declared": {
                "direct": {name: direct[name] for name in route},
                "documents": declared_documents,
                "fanout": len(declared_documents),
                "distinct": len(declared_counts),
                "repeated": {
                    key: value for key, value in declared_counts.items() if value > 1
                },
            },
            "effective": {
                "documents": effective_documents,
                "fanout": len(effective_documents),
                "distinct": len(effective_counts),
                "repeated": {
                    key: value for key, value in effective_counts.items() if value > 1
                },
            },
        }
    return {
        "direct": direct,
        "conditional": conditional,
        "conditional_triggers": trigger_report,
        "duplicate_unconditional_doctrine": {
            key: value for key, value in sorted(direct_counts.items()) if value > 1
        },
        "replaceable_exact_prose_assertions": exact_assertions,
        "projected_routes": projected,
    }


class PluginBehaviorTests(unittest.TestCase):
    def test_manifest_and_public_skills(self):
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "cse")
        self.assertEqual(manifest["version"], "2.3.0")
        self.assertEqual(
            manifest["interface"]["displayName"],
            "Agentic Computational Science and Engineering",
        )
        self.assertEqual({path.name for path in (ROOT / "skills").iterdir()}, CORE)
        self.assertEqual({path.name for path in (SOURCES_ROOT / "skills").iterdir()}, SOURCES)
        self.assertEqual({path.name for path in (VISUALIZE_ROOT / "skills").iterdir()}, VISUALIZE)
        self.assertEqual(json.loads((SOURCES_ROOT / ".codex-plugin/plugin.json").read_text())["version"], "1.0.0")
        self.assertEqual(json.loads((VISUALIZE_ROOT / ".codex-plugin/plugin.json").read_text())["version"], "2.0.0")
        self.assertTrue((ROOT / "BANNED.md").is_file())

    def test_release_assurance_stays_bounded_and_pinned(self):
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(manifest["version"], "2.3.0")
        routing = yaml.safe_load((ROOT / "evaluation/skill-routing.yaml").read_text())
        cases = routing["cases"]
        self.assertGreaterEqual(len(cases), 15)
        self.assertEqual(28, len(cases))
        self.assertEqual(len(cases), len({case["id"] for case in cases}))
        self.assertEqual(
            {"direct", "indirect", "incomplete", "negative", "unsupported"},
            {case["category"] for case in cases},
        )
        required = {
            "id", "category", "prompt", "expected_skill",
            "expected_initial_action", "prohibited_action",
        }
        skill_sets = {
            "cse": CORE,
            "cse-sources": SOURCES,
            "cse-visualize": VISUALIZE,
        }
        for case in cases:
            self.assertLessEqual(required, set(case))
            if case["expected_skill"] is not None:
                namespace, name = case["expected_skill"].split(":", 1)
                self.assertIn(namespace, skill_sets)
                self.assertIn(name, skill_sets[namespace])
        recorded = "\n".join(path.read_text() for path in (ROOT / "evaluation/results").glob("*.md"))
        recorded_ids = set(re.findall(r"^\| ([^ |]+) \| Pass \|", recorded, re.MULTILINE))
        self.assertLessEqual(recorded_ids, {case["id"] for case in cases})

    def test_every_skill_declares_small_valid_reference_routes(self):
        for name in SKILLS:
            frontmatter = skill_frontmatter(name)
            metadata = frontmatter["metadata"]
            routing = metadata["cse-routing"]
            direct = routing["direct"]
            conditional = routing["conditional"]
            paths = route_paths(name)
            self.assertTrue(direct)
            self.assertTrue(set(direct) <= set(paths))
            self.assertTrue(set(conditional) <= set(paths))
            self.assertTrue(set(direct).isdisjoint(conditional))
            self.assertIn("operating-model" if name in CORE else "handoff", direct)
            for reference in (*direct, *conditional):
                self.assertTrue((skill_root(name) / paths[reference]).is_file(), reference)
            if name in WORKFLOW_ORDERS:
                self.assertTrue(frontmatter["description"].startswith(
                    f"CSE Workflow {WORKFLOW_ORDERS[name]} —"
                ))
            else:
                self.assertTrue(frontmatter["description"].startswith(
                    f"CSE {'Supporting Audit' if name in SUPPORTING else 'Visualize' if name in VISUALIZE else 'Sources'} —"
                ))
            self.assertLessEqual(len(skill_text(name).splitlines()), 80)
            self.assertNotIn("[" + "TODO", skill_text(name))

    def test_skill_ui_metadata_remains_a_discovery_interface(self):
        for name in SKILLS:
            interface = yaml.safe_load((skill_root(name) / "skills" / name / "agents/openai.yaml").read_text())["interface"]
            self.assertRegex(interface["display_name"], r"^CSE: ")
            self.assertRegex(interface["short_description"], r"^.{25,64}$")
            namespace = "cse-sources" if name in SOURCES else "cse-visualize" if name in VISUALIZE else "cse"
            self.assertTrue(interface["default_prompt"].startswith(f"Use ${namespace}:"))

    def test_durable_prose_routes_reach_both_language_references(self):
        for name in DURABLE_PROSE_SKILLS:
            routing = skill_frontmatter(name)["metadata"]["cse-routing"]
            self.assertNotIn("terminology", routing["direct"], name)
            self.assertNotIn("BANNED", routing["direct"], name)
            self.assertTrue({"terminology", "BANNED"} <= set(routing["conditional"]), name)
            text = skill_text(name)
            self.assertRegex(text, r"(?is)activate\s+`terminology`.*`references/terminology\.md`")
            self.assertRegex(text, r"(?is)activate.*`BANNED`.*`BANNED\.md`")
            self.assertRegex(text, r"(?is)routine\s+inspection.*questions.*commands.*terse progress")

    def test_terminology_conflict_and_native_approval_safeguards_remain_explicit(self):
        cases = yaml.safe_load((ROOT / "evaluation" / "skill-routing.yaml").read_text())["cases"]
        by_id = {case["id"]: case for case in cases}
        conflict = by_id["setup-terminology-conflict"]
        conflict_text = f"{conflict['expected_initial_action']} {conflict['prohibited_action']}".lower()
        self.assertEqual(conflict["expected_skill"], "cse:setup")
        self.assertIn("scoped", conflict_text)
        self.assertIn("unresolved", conflict_text)
        self.assertIn("silently", conflict_text)
        self.assertIn("approval", conflict_text)

        zotero_case = by_id["unsupported-zotero-write"]
        zotero_text = f"{zotero_case['expected_initial_action']} {zotero_case['prohibited_action']}".lower()
        self.assertEqual(zotero_case["expected_skill"], "cse-sources:zotero")
        self.assertIn("approval", zotero_text)
        self.assertIn("read-only", zotero_text)
        self.assertIn("modify", zotero_text)
        self.assertIn("native approval immediately before the write", skill_text("zotero"))

    def test_routing_analysis_is_deterministic_and_keeps_projection_counts(self):
        report = routing_analysis()
        self.assertEqual(
            {"terminology": "references/terminology.md", "BANNED": "BANNED.md"},
            {key: ROUTE_PATHS[key] for key in ("terminology", "BANNED")},
        )
        self.assertTrue(report["replaceable_exact_prose_assertions"])
        self.assertGreater(report["duplicate_unconditional_doctrine"]["operating-model"], 1)
        for route in report["projected_routes"].values():
            declared = route["declared"]
            effective = route["effective"]
            declared_documents = declared["documents"]
            effective_documents = effective["documents"]
            self.assertEqual(
                len(declared_documents),
                declared["distinct"] + sum(
                    count - 1 for count in declared["repeated"].values()
                ),
            )
            self.assertEqual(declared_documents, projected_documents(route["route"]))
            self.assertEqual(effective_documents, effective_projected_documents(route["route"]))
            self.assertEqual(len(declared_documents), declared["fanout"])
            self.assertGreater(declared["repeated"].get("references/operating-model.md", 0), 1)
            self.assertEqual(effective["fanout"], effective["distinct"])
            self.assertEqual(effective["repeated"], {})
            self.assertEqual(len(effective_documents), len(set(effective_documents)))
            self.assertLessEqual(effective["distinct"], 12)

    def test_conditional_references_have_local_triggers(self):
        for name in SKILLS:
            text = skill_text(name)
            conditional = skill_frontmatter(name)["metadata"]["cse-routing"]["conditional"]
            for reference in conditional:
                self.assertRegex(
                    text,
                    rf"(?i)(?:activate|when|for|selected|scope|conditional).{{0,180}}{re.escape(reference)}",
                    f"{name} does not explain when {reference} is used",
                )

    def test_operating_model_owns_strengths_alignment_handoffs_and_reuse(self):
        text = (ROOT / "references/operating-model.md").read_text()
        for phrase in (
            "Must — invariant", "Should — default", "May — option",
            "At an initial workflow entrypoint", "Ask only\nquestions",
            "internal CSE handoff inherits", "must not reread an unchanged",
            "fresh reviewer independently loads", "working notebook",
            "Review inspects that complete notebook", "material changes",
            "durable CSE-authored scientific prose", "Routine inspection",
        ):
            self.assertIn(phrase, text)
        self.assertNotIn("terminology.md` and `../BANNED.md` completely", text)

    def test_declared_projection_preserves_reads_and_effective_handoffs_reuse(self):
        research = ["research", "design", "build", "analyze", "summarize", "review"]
        diagnose = ["diagnose", *research]
        diagnose_documents = projected_documents(diagnose)
        diagnose_counts = Counter(diagnose_documents)
        self.assertGreater(diagnose_counts["references/operating-model.md"], 1)
        self.assertEqual(12, len(set(diagnose_documents)))
        for route in (research, diagnose):
            effective = effective_projected_documents(route)
            self.assertEqual(len(effective), len(set(effective)))
            self.assertLessEqual(len(effective), 12)
        self.assertNotIn("data", skill_frontmatter("analyze")["metadata"]["cse-routing"]["direct"])
        self.assertEqual(skill_frontmatter("setup")["metadata"]["cse-routing"]["direct"], ["operating-model"])
        self.assertNotIn("latex-packages", skill_frontmatter("summarize")["metadata"]["cse-routing"]["direct"])

    def test_workflow_boundaries_and_conditional_routes(self):
        research = skill_text("research")
        self.assertIn("capability-aware plan", research)
        self.assertIn("Add a query only when", research)
        self.assertNotIn("exactly one direct query", research)
        diagnose = skill_text("diagnose")
        self.assertIn("not evidence that the physical model", diagnose)
        self.assertIn("Do not change implementation", diagnose)
        design = skill_text("design")
        self.assertIn("bounded supported design", design)
        self.assertIn("publish and verify one issue", design)
        self.assertIn("Only a **Ready**", design)
        build = skill_text("build")
        self.assertIn("one change-accounting run against the final tree", build)
        self.assertIn("stage performing a Git or GitHub action owns its authority", build)
        analyze = skill_text("analyze")
        self.assertIn("an authoritative retained input\nneeds no Data probe", analyze)
        self.assertIn("Project-selected output formats", analyze)
        self.assertIn("A CSV or summary statistic does not replace the figure", analyze)
        review = skill_text("review")
        self.assertIn("Result lens", review)
        self.assertIn("Capability lens", review)
        self.assertIn("explicit merge base", review)
        self.assertIn("complete changed functions", review)
        summarize = skill_text("summarize")
        self.assertIn("useful method-specific result", summarize)
        self.assertIn("before Review", summarize)
        self.assertIn("neither a CSV link nor a table replaces it", summarize)

    def test_scientific_safety_and_retained_evidence_boundaries_remain(self):
        data = skill_text("data")
        self.assertIn("Read-only requests do not mutate", data)
        self.assertRegex(data, r"repairing values\s+silently")
        zotero = skill_text("zotero")
        self.assertIn("native approval immediately before the write", zotero)
        mathpix = skill_text("mathpix")
        self.assertIn("transcription, not validated scientific truth", mathpix)
        plot = skill_text("plot")
        self.assertIn("retained continuous relationship", plot)
        self.assertIn("`o`/`x` points", plot)
        quarto = skill_text("quarto")
        self.assertIn("execute.enabled: false", quarto)
        self.assertIn("--no-execute", quarto)
        self.assertIn("Ordinary Quarto HTML", quarto)
        self.assertIn("scaffold.sh", quarto)
        self.assertIn("promoted-pdf", quarto)

    def test_three_sections_and_review_lenses_keep_ownership_boundaries(self):
        operating = (ROOT / "references/operating-model.md").read_text()
        for term in ("Think", "Do", "Publish", "Setup runs once", "Audit stands outside"):
            self.assertIn(term, operating)
        review = skill_text("review")
        summarize = skill_text("summarize")
        self.assertLess(len(review.split()), 340)
        self.assertLess(len(summarize.split()), 330)
        self.assertEqual(skill_frontmatter("review")["metadata"]["cse-routing"]["direct"], ["operating-model"])
        for phrase in (
            "calculations stay with the accepted numerical owner",
            "distinct fields do not reuse one value without identity evidence",
            "missing inputs and silent exits preserve causes",
            "repeated constants,\nlimits, defaults, and tolerances use their existing scientific owner",
        ):
            self.assertIn(phrase, review)
        self.assertIn("chat summary of the main points", summarize)
        surface = (ROOT / "references/code-surface-review.md").read_text()
        self.assertIn("Any implementation correction\ninvalidates the", surface)
        audit = skill_text("audit")
        for phrase in (
            "scientific calculations or transformations outside the designated owner",
            "result mapping that duplicates, fabricates, drops, or changes the meaning",
            "silent exits that erase failure or unavailability causes",
            "duplicated equations, physical limits, constants, defaults, or tolerances",
            "semantically distinct fields populated from one source without identity evidence",
        ):
            self.assertIn(phrase, audit)

    def test_visualize_active_surface_is_html_first_without_retired_companion(self):
        retired = "reveal" + "js"
        self.assertFalse((VISUALIZE_ROOT / "skills" / retired).exists())
        self.assertFalse((VISUALIZE_ROOT / "references" / f"{retired}.md").exists())
        active = "\n".join(
            path.read_text(errors="replace")
            for path in VISUALIZE_ROOT.rglob("*") if path.is_file()
        ).casefold()
        self.assertNotIn(retired, active)
        self.assertIn("ordinary quarto html", active)
        self.assertIn("promoted-pdf-header.tex", active)

    def test_scientific_doctrine_and_test_boundaries_remain_reachable(self):
        numerical = (ROOT / "references/numerical-testing.md").read_text()
        failure = (ROOT / "references/failure-triage.md").read_text()
        projects = (ROOT / "references/scientific-projects.md").read_text()
        github = (ROOT / "references/github-and-git.md").read_text()
        decisions = (ROOT / "references/decision-records.md").read_text()
        dependent = (ROOT / "references/dependent-scientific-changes.md").read_text()
        design = skill_text("design")
        for text, terms in (
            (numerical, ("result-first", "reference case", "tolerance rationale", "Coverage may reveal", "never by weakening a tolerance", "failing case, proposed")),
            (failure, ("method that actually ran", "no useful numerical result",
                       "key/value failure record", "input-readiness question",
                       "bounded direct")),
            (projects, ("defaults to the root-level", "repository-relative path",
                        "meaningful populated child names", "same responsibilities",
                        "exist before Review", "must not rerun", "one claim-led figure",
                        "The retained CSV owns")),
            (github, ("Standalone issues are normal", "git merge --ff-only", "optional context")),
            (decisions, ("one numbered sequence", "reversible library choice", "independent reference case")),
            (dependent, ("Observed state", "Proposed correction")),
            (design, ("Result lens", "Capability lens", "Only a **Ready** disposition permits `cse:build`")),
        ):
            for term in terms:
                self.assertIn(term, text)
        for name in ("analyze", "build", "review"):
            self.assertIn("failure-triage", skill_frontmatter(name)["metadata"]["cse-routing"]["conditional"])
        setup = skill_text("setup")
        self.assertIn("do not rename or migrate it solely", setup)
        self.assertIn("`analyses/<short-id>/{inputs,scripts,results,figures}`", setup)
        design = skill_text("design")
        self.assertRegex(design, r"(?is)publish.*one issue.*before.*Build")
        self.assertRegex(design, r"(?is)only a \*\*Ready\*\*.*permits")

    def test_issue_54_moves_design_review_and_binds_failing_cases(self):
        design = skill_text("design")
        build = skill_text("build")
        dependent = (ROOT / "references/dependent-scientific-changes.md").read_text()
        decisions = (ROOT / "references/decision-records.md").read_text()
        numerical = (ROOT / "references/numerical-testing.md").read_text()
        routing = yaml.safe_load((ROOT / "evaluation/skill-routing.yaml").read_text())["cases"]
        by_id = {case["id"]: case for case in routing}

        self.assertLess(len(design.split()), 520)
        self.assertLess(len(dependent.split()), 600)
        self.assertNotIn("## Independent pre-Build review", dependent)
        self.assertNotIn("## Pre-Build disposition", dependent)
        self.assertIn("result or a capability", design)
        self.assertIn("Experiment issue (result)", design)
        self.assertIn("Tool issue (capability)", design)
        self.assertIn("no code, registries, generators, or prescribed implementation", design)
        self.assertIn("no new numerical method, tolerance", build)
        self.assertIn("cse:diagnose` classifies the", build)
        self.assertIn("same approval as the fix", numerical)
        self.assertIn("records five facts", decisions)
        self.assertNotIn("Four focused kinds", decisions)
        self.assertNotIn("scientific-formulation`:", decisions)
        self.assertNotIn("numerical-method`:", decisions)
        self.assertEqual("cse:design", by_id["design-experiment-result-shape"]["expected_skill"])
        self.assertEqual("cse:design", by_id["design-capability-tool-shape"]["expected_skill"])
        self.assertEqual("cse:diagnose", by_id["build-failing-case-diagnose-boundary"]["expected_skill"])
        templates = ROOT / "assets/project/adr/templates"
        self.assertFalse(templates.exists() and any(templates.iterdir()))

    def test_document_and_figure_routes_preserve_render_and_disposition_rules(self):
        latex = skill_text("latex")
        quarto = skill_text("quarto")
        plot = skill_text("plot")
        summarize = skill_text("summarize")
        profile = (VISUALIZE_ROOT / "references/latex-article-profiles.md").read_text()
        plotting = (VISUALIZE_ROOT / "references/plotting.md").read_text()
        for text, patterns in (
            (latex, (r"one\s+retained data authority", r"never authorizes.*model execution", r"visual")),
            (quarto, (r"execute\.enabled: false", r"--no-execute", r"scaffold\.sh", r"material.*return to `cse:review`")),
            (plot, (r"retained continuous relationship", r"`o`/`x`", r"project.*intended use")),
            (summarize, (r"useful method-specific result", r"must\s+not\s+rerun", r"before Review")),
            (profile, (r"Manuscript", r"Analysis research notebook", r"one continuous story", r"selected render")),
            (plotting, (r"primary figure directly answers", r"Predictions available only", r"color-vision-safe")),
        ):
            for pattern in patterns:
                self.assertRegex(text, rf"(?is){pattern}")

    def test_issue_24_material_review_gate_keeps_all_dispositions(self):
        routing = yaml.safe_load((ROOT / "evaluation/skill-routing.yaml").read_text())
        cases = {
            case["expected_disposition"]: case
            for case in routing["cases"] if case.get("source_issue") == 24
        }
        self.assertEqual({"Ready", "Revise", "Block"}, set(cases))
        guide = skill_text("design")
        design = skill_text("design")
        for disposition, case in cases.items():
            self.assertEqual("cse:design", case["expected_skill"])
            self.assertIn("Build", case["prohibited_action"])
            self.assertIn(f"**{disposition}**", guide)
        for term in (
            "live project", "callers, owners", "evidence",
            "public input", "Result lens", "Capability lens", "two fresh reviewers",
            "normal GitHub issue record",
        ):
            self.assertIn(term, guide)
        self.assertRegex(design, r"(?is)only a \*\*Ready\*\*.*permits `cse:build`")

    def test_issue_15_protocol_is_fully_pinned(self):
        config = json.loads((ROOT / "evaluation/cooling-fit/benchmark.json").read_text())
        oracle = config["oracle"]
        self.assertEqual({
            "version": 1,
            "observations_sha256": "928d3f676e247c572b3d8c81ebc0ff64f20f67dadd3bfdac406f58c4eda7206f",
            "equation": "T(t) = T_ambient + (T_initial - T_ambient) exp(-k t)",
            "method": "positive one-parameter nonlinear least squares with fixed ambient and initial temperatures",
            "ambient_degC": 22.0, "initial_degC": 90.0,
            "k_per_s": 0.00499692115269, "time_constant_s": 200.123229774,
            "rmse_degC": 0.162902517152, "standard_error_k_per_s": 0.0000141073234294,
            "linearized_95_interval_k_per_s": [0.00496927079877, 0.00502457150661],
            "tolerances": {
                "k_per_s": 0.000005, "time_constant_s": 0.5, "rmse_degC": 0.01,
                "standard_error_k_per_s": 0.000002, "interval_k_per_s": 0.00003,
            },
        }, {key: oracle[key] for key in (
            "version", "observations_sha256", "equation", "method", "ambient_degC",
            "initial_degC", "k_per_s", "time_constant_s", "rmse_degC",
            "standard_error_k_per_s", "linearized_95_interval_k_per_s", "tolerances",
        )})
        self.assertEqual(
            "Determine the missing cooling-rate parameter from the retained observations, complete the scientific work in this repository, and report the supported result; use the supplied project decisions and do not ask for clarification during this run.",
            config["prompt"],
        )
        self.assertEqual({
            "k_per_s": "One third of the linearized standard error; allows solver serialization but rejects a materially different fit.",
            "time_constant_s": "Propagation of the accepted k tolerance gives about 0.20 s; 0.5 s also allows ordinary display rounding.",
            "rmse_degC": "Below one tenth of the retained observation noise scale while allowing serialization differences.",
            "standard_error_k_per_s": "Allows equivalent Jacobian and residual-variance implementations without admitting the seconds/minutes defect.",
            "interval_k_per_s": "Allows equivalent nonlinear and through-origin linearized residual intervals while remaining far below the seconds/minutes defect.",
        }, oracle["tolerance_rationale"])
        self.assertEqual(
            {
                "research": ["cse:research", "cse:design", "cse:build", "cse:analyze", "cse:summarize", "cse:review"],
                "diagnose": ["cse:diagnose", "cse:research", "cse:design", "cse:build", "cse:analyze", "cse:summarize", "cse:review"],
            }, {key: config["cases"][key]["expected_route"] for key in ("research", "diagnose")})
        tree = ast.parse((ROOT / "scripts/cooling_fit_benchmark.py").read_text())
        gate_dicts = [
            node for node in ast.walk(tree) if isinstance(node, ast.Dict)
            and {key.value for key in node.keys if isinstance(key, ast.Constant)}
            >= {"remote_safety", "retained_numerical_evidence", "research_source_support"}
        ]
        self.assertEqual(1, len(gate_dicts))
        self.assertEqual(
            {"remote_safety", "retained_numerical_evidence", "research_source_support",
             "notebook_before_review", "nonexecuting_supported_notebook"},
            {key.value for key in gate_dicts[0].keys},
        )
        category_weights = Counter()
        for item in config["rubric"]:
            category_weights[item["category"]] += item["max_points"]
        self.assertEqual({
            "evidence_justified_entry": 15, "design_build_analyze": 30,
            "review_of_notebook": 20, "notebook_and_response": 20,
            "restraint": 10, "efficiency": 5,
        }, dict(category_weights))
        self.assertEqual(100, sum(category_weights.values()))
        self.assertEqual(
            ["entry_route", "design_issue", "numerical_execution", "independent_review",
             "analysis_notebook", "restraint", "efficiency"],
            [item["id"] for item in config["rubric"] if item["owner"] == "objective"],
        )
        source = (ROOT / "scripts/cooling_fit_benchmark.py").read_text()
        for relative in (
            "inputs/observations.csv", "results/fit_summary.json", "results/fit_curve.csv",
            "results/plot_manifest.json", "figures/cooling_fit.png", "notebook.qmd",
            "notebook.html",
        ):
            self.assertIn(Path(relative).name, source)

    def test_reference_cleanup_breaks_transitive_full_stack_reads(self):
        for relative in (
            "references/latex-figures.md", "references/latex-packages.md",
            "references/latex-article-profiles.md", "references/quarto-execution.md",
        ):
            text = (VISUALIZE_ROOT / relative).read_text()
            self.assertNotRegex(text, r"(?i)read `[^`]+` completely")
        self.assertIn("consult the relevant section", (VISUALIZE_ROOT / "references/latex-figures.md").read_text())

    def test_scientific_project_and_review_owners_remain_explicit(self):
        projects = (ROOT / "references/scientific-projects.md").read_text()
        self.assertIn("exist before Review", projects)
        self.assertIn("still requires investigator", projects)
        dependent = (ROOT / "references/dependent-scientific-changes.md").read_text()
        design = skill_text("design")
        self.assertNotIn("bounded supported design", dependent)
        self.assertIn("bounded supported design", design)
        self.assertIn("two fresh reviewers", design)
        surface = (ROOT / "references/code-surface-review.md").read_text()
        self.assertIn("Build owns the one change-accounting run", surface)
        self.assertIn("Build reports its changed surface", surface)

    def test_source_only_boundary_excludes_runs_from_sync_and_installation(self):
        benchmark = (ROOT / "scripts/cooling_fit_benchmark.py").read_text()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            staged = Path(directory) / "staged"
            shutil.copytree(
                ROOT,
                source,
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"),
            )
            (source / ".runs/cooling-fit/run-1").mkdir(parents=True)
            (source / ".runs/cooling-fit/run-1/events.jsonl").write_text("source-only\n")
            result = subprocess.run(
                [
                    "python3", str(source / "scripts/package_inventory.py"),
                    "stage", "cse", str(staged), "--commit", "0" * 40,
                    "--home", str(Path(directory) / "home"),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            identity = json.loads(result.stdout)
            self.assertEqual(
                identity["payloadSkills"],
                [
                    "audit", "setup", "research", "diagnose", "design",
                    "build", "analyze", "summarize", "review", "write",
                ],
            )
            self.assertFalse((staged / ".runs").exists())
            self.assertFalse((staged / "tests").exists())
            self.assertFalse((staged / "extensions").exists())
            self.assertFalse((staged / "evaluation").exists())
        self.assertIn('".runs"', benchmark)
        self.assertIn("reference_reads", benchmark)

    def test_runtime_surface_has_no_banned_or_retired_workflow_material(self):
        roots = [
            ROOT / ".codex-plugin", ROOT / "skills", ROOT / "references", ROOT / "assets",
            SOURCES_ROOT, VISUALIZE_ROOT,
        ]
        text = "\n".join(
            path.read_text(errors="replace")
            for root in roots for path in root.rglob("*") if path.is_file()
        ).casefold()
        self.assertNotIn("arti" + "fact", text)
        self.assertNotIn("datalad", text)
        self.assertNotIn("git-annex", text)
        self.assertNotRegex(text, r"\$(?:project-truss|mattpocock|superpowers)")

    def test_companion_package_ownership_namespaces_and_handoffs(self):
        packages = {
            "cse": (ROOT, CORE, "2.3.0"),
            "cse-sources": (SOURCES_ROOT, SOURCES, "1.0.0"),
            "cse-visualize": (VISUALIZE_ROOT, VISUALIZE, "2.0.0"),
        }
        for name, (root, expected, version) in packages.items():
            package_manifest = json.loads((root / ".codex-plugin/plugin.json").read_text())
            self.assertEqual((package_manifest["name"], package_manifest["version"]), (name, version))
            self.assertEqual({path.name for path in (root / "skills").iterdir()}, expected)

        active_roots = [ROOT / "skills", ROOT / "references", ROOT / ".codex-plugin", ROOT / "README.md", ROOT / "docs/design", ROOT / "evaluation", ROOT / "examples", ROOT / "extensions"]
        active = "\n".join(
            path.read_text(errors="replace")
            for root in active_roots
            for path in ([root] if root.is_file() else root.rglob("*"))
            if path.is_file() and "results" not in path.parts and "cse-pi-harness" not in path.parts
        )
        forbidden = ["cse" + ":" + name for name in sorted(SOURCES | VISUALIZE)]
        self.assertEqual([], [identifier for identifier in forbidden if identifier in active])

        sources = (SOURCES_ROOT / "references/handoff.md").read_text()
        visualize = (VISUALIZE_ROOT / "references/handoff.md").read_text()
        for text, diagnostic in (
            (sources, "CSE Sources requires the core cse plugin"),
            (visualize, "CSE Visualize requires the core cse plugin"),
        ):
            self.assertIn(diagnostic, text)
            self.assertIn("was not", text)
            self.assertIn("cache, deployment,", " ".join(text.split()))
        self.assertIn("does not require or invoke CSE Visualize", sources)
        self.assertIn("does not require or invoke CSE Sources", visualize)
        for name in SOURCES | VISUALIZE:
            family = "Sources" if name in SOURCES else "Visualize"
            text = skill_text(name)
            self.assertIn("Before any other action", text)
            self.assertIn(f"CSE {family} requires the core cse plugin", text)
            self.assertIn("was not", text)
            self.assertNotIn("claim_strength", text)
        self.assertNotIn(
            "plotting",
            skill_frontmatter("digitize")["metadata"]["cse-routing"]["direct"],
        )

    def test_companion_configuration_matrix_covers_supported_routes(self):
        matrix = yaml.safe_load((ROOT / "evaluation/companion-routing.yaml").read_text())["configurations"]
        self.assertEqual(
            {"core-only", "core-sources", "core-visualize", "full", "companion-without-core"},
            {case["id"] for case in matrix},
        )

    def test_workbench_research_uses_current_three_package_inventory(self):
        paths = (
            ROOT / "docs/workbench-research/README.md",
            ROOT / "docs/workbench-research/PI-FEASIBILITY.md",
            ROOT / "docs/workbench-research/PI-ECOSYSTEM-AUDIT.md",
        )
        for path in paths:
            text = " ".join(path.read_text().casefold().split())
            self.assertIn("nine core", text)
            self.assertIn("four optional sources", text)
            self.assertIn("six optional visualize", text)
            self.assertNotIn("eight workflow", text)
            self.assertNotIn("seven optional visualize", text)


if __name__ == "__main__":
    unittest.main()
