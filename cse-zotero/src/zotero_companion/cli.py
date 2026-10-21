"""Command-line entry point for CSE Zotero."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from .acquire import AcquireStop, acquire, configured_tokens
from .connector_job import connector_status
from .better_bibtex import BetterBibTeXClient, BetterBibTeXError, configure_export, export_plan
from .config import (
    ConfigError,
    config_payload,
    default_config_path,
    _read_config_snapshot,
    load_config,
    proposed_config,
    write_config,
)
from .corpus_migration import CorpusMigrationError, migrate_corpus
from .coverage import CoverageError, coverage_report
from .evidence_sync import EvidenceSyncError, sync_evidence
from .local_api import LocalAPIError, ZoteroLocalAPI
from .maintenance import maintain_wiki
from .mathpix_ops import MathpixOperationError, mathpix_conversion
from .manifests import ManifestError, lint_manifests, load_manifests, manifest_lookup
from .plugin_client import PluginClientError, ZoteroPluginClient
from .projects import (
    SLUG,
    ProjectError,
    default_registry_path,
    load_registry,
    plan_registration,
    project_collections,
    sync_projects,
    write_registry,
)
from .health import health_report
from .records import (
    RecordError,
    global_context,
    lineage,
    lint_records,
    record_lookup,
    search_records,
)
from .release import ReleaseError, release_plan
from .registry_migration import RegistryMigrationError, build_registry_pack
from .report import audit_payload, doctor_payload
from .scientific_data import (
    ScientificDataError,
    query_table,
    register_package,
    search_registry,
    select_resource,
    validate_catalog,
)
from .source_ops import attachment_path, search_sources, source_children
from .templates import paper_brief_template, record_template
from .wiki import (
    WikiError,
    WikiSnapshot,
    classify_source,
    context_pack,
    evidence_passages,
    index_wiki,
    materialize_snapshot,
    search_wiki,
    source_record,
    stale_report,
    triage_wiki,
    verify_wiki,
)
from .writer import DEFAULT_KEY_PATH, WriterError, ZoteroLocalAPIWriter


def add_writer_options(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--key-file",
        type=Path,
        default=DEFAULT_KEY_PATH,
        help="path to the remembered Zotero local API key",
    )
    command.add_argument("--json", action="store_true", help="emit JSON")


def add_wiki_options(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--wiki-root",
        type=Path,
        default=None,
        help="agent wiki directory (default: configured local corpus/wiki)",
    )
    command.add_argument("--json", action="store_true", help="emit JSON")


def emit_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _project_command(args: argparse.Namespace) -> dict:
    registry_path = args.registry or default_registry_path()
    registry = load_registry(registry_path)
    if args.command == "project-list":
        pages = args.wiki_root / "projects"
        return {
            "registry": str(registry_path),
            "root_collection": registry["root_collection"],
            "projects": {
                slug: {**entry, "page": str(pages / f"{slug}.md")}
                for slug, entry in sorted(registry["projects"].items())
            },
        }
    api = ZoteroLocalAPI()
    if args.command == "project-sync":
        return sync_projects(
            registry,
            args.wiki_root,
            collections=api.collections(),
            items=api.items(top_level=True),
            slug=args.slug,
            apply=args.apply,
        )
    if args.command == "project-organize":
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        result = ZoteroPluginClient().project_organize(plan, apply=args.apply)
        if args.apply and plan.get("project"):
            result["sync"] = sync_projects(
                registry,
                args.wiki_root,
                collections=api.collections(),
                items=api.items(top_level=True),
                slug=plan["project"],
                apply=True,
            )
        return result
    collection = args.collection
    created = None
    if args.create:
        # The add-on reads the root from the registry file, so it must be recorded.
        if not registry["root_collection"] or args.root not in (None, registry["root_collection"]):
            raise ProjectError("--create needs an already registered root collection; register one with --root and --collection first")
        # Check before creating, so a rejected registration leaves nothing behind in Zotero.
        if not SLUG.fullmatch(args.slug) or args.slug in registry["projects"]:
            raise ProjectError(f"--create needs a new, valid project slug; {args.slug!r} is invalid or already registered")
        plan = {"operations": [{"op": "create", "name": args.create}]}
        created = ZoteroPluginClient().project_organize(plan, apply=args.apply)
        if not args.apply:
            return {"mode": "dry-run", "create": created, "slug": args.slug, "repository": args.repository}
        collection = created["applied"][0]["key"]
    proposed = plan_registration(
        registry,
        slug=args.slug,
        collection=collection,
        repository=args.repository,
        collections=api.collections(),
        root=args.root,
    )
    payload = {
        "mode": "apply" if args.apply else "dry-run",
        "registry": str(registry_path),
        "current": registry["projects"].get(args.slug),
        "proposed": proposed["projects"][args.slug],
        "root_collection": proposed["root_collection"],
    }
    if created:
        payload["created"] = created
    if args.apply:
        write_registry(proposed, registry_path)
        payload["sync"] = sync_projects(
            proposed,
            args.wiki_root,
            collections=api.collections(),
            items=api.items(top_level=True),
            slug=args.slug,
            apply=True,
        )
    return payload


def _project_doctor(config, zotero_ok: bool) -> dict:
    try:
        registry = load_registry()
    except ProjectError as exc:
        return {"error": str(exc)}
    observed: dict = {"registered": sorted(registry["projects"]), "root_collection": registry["root_collection"]}
    if zotero_ok and config is not None and registry["projects"]:
        try:
            api = ZoteroLocalAPI()
            result = sync_projects(
                registry, config.wiki_root, collections=api.collections(), items=api.items(top_level=True)
            )
            observed["stale"], observed["missing"] = result["stale"], result["missing"]
        except (ProjectError, LocalAPIError) as exc:
            observed["error"] = str(exc)
    try:
        observed["addon_sync"] = ZoteroPluginClient().status().get("projectSync")
    except PluginClientError:
        observed["addon_sync"] = None
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(prog="cse-zotero")
    subparsers = parser.add_subparsers(dest="command", required=True)
    acquire_cmd = subparsers.add_parser("acquire", help="add one paper, with publisher safeguards")
    acquire_cmd.add_argument("identifier")
    acquire_cmd.add_argument("--collection", help="existing collection key or unambiguous name")
    acquire_cmd.add_argument("--dry-run", action="store_true")
    acquire_cmd.add_argument("--route", choices=("auto", "browser"), default="auto", help="force native Connector route for one paper")
    acquire_cmd.add_argument("--json", action="store_true")
    doctor = subparsers.add_parser("doctor", help="report installed protocol and capability readiness")
    doctor.add_argument("--config", type=Path, default=default_config_path())
    doctor.add_argument("--json", action="store_true")
    initialize = subparsers.add_parser("init", help="plan or initialize user-owned CSE Zotero configuration")
    initialize.add_argument("--config", type=Path, default=default_config_path())
    initialize.add_argument("--corpus-root", type=Path)
    initialize.add_argument("--apply", action="store_true")
    initialize.add_argument(
        "--preview-sha256",
        help="SHA-256 token from init dry-run; required when applying a changed existing configuration",
    )
    initialize.add_argument(
        "--mathpix-consent",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="record or withdraw library-wide Mathpix consent; fresh apply requires an explicit choice",
    )
    initialize.add_argument("--json", action="store_true")
    bibliography = subparsers.add_parser(
        "bibliography-export", help="plan or refresh the canonical Better BibTeX library export"
    )
    bibliography.add_argument("--config", type=Path, default=default_config_path())
    bibliography.add_argument("--apply", action="store_true")
    bibliography.add_argument("--json", action="store_true")
    zotero_search = subparsers.add_parser("zotero-search", help="search live top-level Zotero sources")
    zotero_search.add_argument("query")
    zotero_search.add_argument("--limit", type=int, default=25)
    zotero_search.add_argument("--json", action="store_true")
    zotero_children = subparsers.add_parser("zotero-children", help="list live children of one Zotero parent")
    zotero_children.add_argument("parent_key")
    zotero_children.add_argument("--json", action="store_true")
    zotero_path = subparsers.add_parser("zotero-attachment-path", help="resolve one live Zotero attachment path")
    zotero_path.add_argument("attachment_key")
    zotero_path.add_argument("--json", action="store_true")
    mathpix_convert = subparsers.add_parser("mathpix-convert", help="plan or convert one confirmed Zotero PDF")
    mathpix_convert.add_argument("parent_key")
    mathpix_convert.add_argument("pdf_key")
    mathpix_convert.add_argument("--out", type=Path)
    mathpix_convert.add_argument("--config", type=Path, default=default_config_path())
    mathpix_convert.add_argument("--apply", action="store_true")
    mathpix_convert.add_argument("--json", action="store_true")
    zotero_attach = subparsers.add_parser("zotero-attach-companion", help="plan or attach one linked Markdown child")
    zotero_attach.add_argument("parent_key")
    zotero_attach.add_argument("companion", type=Path)
    zotero_attach.add_argument("--apply", action="store_true")
    add_writer_options(zotero_attach)
    corpus_migrate = subparsers.add_parser(
        "corpus-migrate",
        help="plan or copy the checkout corpus into configured user-owned storage",
    )
    corpus_migrate.add_argument("--config", type=Path, default=default_config_path())
    corpus_migrate.add_argument("--source-root", type=Path, default=Path.cwd())
    corpus_migrate.add_argument("--apply", action="store_true")
    corpus_migrate.add_argument("--json", action="store_true")
    schema_validate = subparsers.add_parser(
        "schema-validate", help="validate scientific data against a LinkML class"
    )
    schema_validate.add_argument("data", type=Path)
    schema_validate.add_argument(
        "--schema", type=Path, help="explicit LinkML schema path (default: packaged companion schema)"
    )
    schema_validate.add_argument("--class", dest="target_class", default="CompanionCatalog")
    schema_validate.add_argument("--json", action="store_true")
    data_query = subparsers.add_parser(
        "data-query", help="run a bounded read-only DuckDB query over a retained table"
    )
    data_query.add_argument("table", type=Path)
    data_query.add_argument("--sql", default="SELECT * FROM records")
    data_query.add_argument("--limit", type=int, default=100)
    data_query.add_argument("--json", action="store_true")
    data_search = subparsers.add_parser(
        "data-search", help="find retained scientific data packages and resolve their resources"
    )
    data_search.add_argument("query", nargs="?", default="", help="terms such as MEA density")
    data_search.add_argument("--registry-root", type=Path, help="thermophysical registry root")
    data_search.add_argument("--limit", type=int, default=20)
    data_search.add_argument("--json", action="store_true")
    data_register = subparsers.add_parser(
        "data-register", help="plan or register one existing scientific data package"
    )
    data_register.add_argument("package", type=Path)
    data_register.add_argument("--registry-root", type=Path, help="existing registry root")
    data_register.add_argument("--supersede", help="explicitly supersede an existing record identity")
    data_register.add_argument("--apply", action="store_true")
    data_register.add_argument("--json", action="store_true")
    data_select = subparsers.add_parser(
        "data-select", help="plan or copy one verified registered resource into an analysis"
    )
    data_select.add_argument("record_id", help="registered package identity")
    data_select.add_argument(
        "--resource",
        default="",
        help="declared or registry-relative resource path (required for multiple resources)",
    )
    data_select.add_argument(
        "--version",
        default="",
        help="registered package version when an identity has revisions",
    )
    data_select.add_argument(
        "--analysis",
        "--analysis-dir",
        dest="analysis",
        type=Path,
        required=True,
        help="analysis directory receiving inputs/",
    )
    data_select.add_argument("--registry-root", type=Path, help="existing registry root")
    select_mode = data_select.add_mutually_exclusive_group()
    select_mode.add_argument("--apply", action="store_true")
    select_mode.add_argument("--dry-run", dest="apply", action="store_false")
    data_select.set_defaults(apply=False)
    data_select.add_argument("--json", action="store_true")
    registry_migrate = subparsers.add_parser(
        "registry-migrate", help="plan or create the thermophysical domain pack"
    )
    registry_migrate.add_argument("registry_root", type=Path)
    registry_migrate.add_argument("--companion-root", type=Path, default=Path("."))
    registry_migrate.add_argument("--apply", action="store_true")
    registry_migrate.add_argument("--json", action="store_true")
    audit = subparsers.add_parser("audit", help="run a read-only Zotero inventory")
    audit.add_argument("--json", action="store_true", help="emit JSON")
    plugin_status = subparsers.add_parser("plugin-status", help="read background plugin status")
    plugin_status.add_argument("--json", action="store_true", help="emit JSON")
    plugin_cleanup = subparsers.add_parser("plugin-tag-cleanup", help="dry-run or explicitly apply tag cleanup")
    plugin_cleanup.add_argument("--apply", action="store_true", help="apply the approved cleanup")
    plugin_cleanup.add_argument("--json", action="store_true", help="emit JSON")
    plugin_searches = subparsers.add_parser("plugin-searches", help="dry-run or explicitly create workflow searches")
    plugin_searches.add_argument("--apply", action="store_true", help="create missing workflow searches")
    plugin_searches.add_argument("--json", action="store_true", help="emit JSON")
    writer_status = subparsers.add_parser("local-status", help="check authenticated local API writer readiness")
    add_writer_options(writer_status)
    writer_tags = subparsers.add_parser("local-tag-cleanup", help="dry-run or apply approved REST tag cleanup")
    writer_tags.add_argument("--apply", action="store_true", help="apply version-checked item tag updates")
    add_writer_options(writer_tags)
    writer_searches = subparsers.add_parser("local-searches", help="dry-run or apply workflow saved-search creation")
    writer_searches.add_argument("--apply", action="store_true", help="create missing workflow saved searches")
    add_writer_options(writer_searches)
    wiki_sync = subparsers.add_parser(
        "wiki-sync",
        help="materialize a read-only Zotero snapshot into the agent wiki",
    )
    wiki_sync.add_argument("--apply", action="store_true", help="write the snapshot and rebuild the index")
    add_wiki_options(wiki_sync)
    wiki_refresh = subparsers.add_parser(
        "wiki-refresh",
        help="explicitly refresh only the generated Zotero source layer",
    )
    wiki_refresh.add_argument(
        "--apply",
        action="store_true",
        help="write generated source records and rebuild the index",
    )
    add_wiki_options(wiki_refresh)
    wiki_maintain = subparsers.add_parser(
        "wiki-maintain",
        help="run one repository-only Zotero wiki maintenance pass",
    )
    wiki_maintain.add_argument(
        "--apply",
        action="store_true",
        help="refresh sources, sync existing companions, and verify the wiki",
    )
    add_wiki_options(wiki_maintain)
    wiki_index = subparsers.add_parser("wiki-index", help="rebuild the agent wiki search index")
    wiki_index.add_argument("--apply", action="store_true", help="write the SQLite index")
    add_wiki_options(wiki_index)
    wiki_search = subparsers.add_parser("wiki-search", help="search materialized Zotero sources")
    wiki_search.add_argument("query", nargs="?", default="", help="text to search")
    wiki_search.add_argument("--project", help="filter by project slug")
    wiki_search.add_argument("--limit", type=int, default=20)
    add_wiki_options(wiki_search)
    wiki_source = subparsers.add_parser("wiki-source", help="read one materialized Zotero source")
    wiki_source.add_argument("key", help="Zotero item key")
    add_wiki_options(wiki_source)
    wiki_evidence = subparsers.add_parser(
        "wiki-evidence",
        help="search existing Markdown evidence companions without PDF conversion",
    )
    wiki_evidence.add_argument("key", help="Zotero parent item key")
    wiki_evidence.add_argument("--query", default="", help="text to find in Markdown companions")
    wiki_evidence.add_argument("--limit", type=int, default=8)
    wiki_evidence.add_argument("--context-lines", type=int, default=2)
    add_wiki_options(wiki_evidence)
    wiki_evidence_sync = subparsers.add_parser(
        "wiki-evidence-sync",
        help="dry-run or materialize existing Zotero Markdown companions",
    )
    wiki_evidence_sync.add_argument(
        "--apply",
        action="store_true",
        help="copy existing .md/.mmd companions into repository evidence bundles",
    )
    wiki_evidence_sync.add_argument(
        "--key",
        dest="keys",
        action="append",
        default=[],
        help="limit sync to one Zotero parent key; repeatable",
    )
    add_wiki_options(wiki_evidence_sync)
    wiki_context = subparsers.add_parser("wiki-context", help="build an agent context pack for a project or the full corpus")
    wiki_context.add_argument("project", nargs="?", help="project slug, for example epcsaft-equilibrium")
    wiki_context.add_argument("--global", dest="global_scope", action="store_true", help="return the full-corpus agent start pack")
    wiki_context.add_argument("--query", default="", help="optional source search within the project")
    wiki_context.add_argument("--limit", type=int, default=12)
    wiki_context.add_argument("--registry-root", type=Path, help="optional thermophysical-data-registry root for link checks")
    add_wiki_options(wiki_context)
    wiki_record = subparsers.add_parser("wiki-record", help="read one typed knowledge record")
    wiki_record.add_argument("record_id", help="stable record ID, for example equation:figiel-born-solvation-shell")
    add_wiki_options(wiki_record)
    wiki_record_search = subparsers.add_parser("wiki-record-search", help="search typed knowledge records")
    wiki_record_search.add_argument("query", nargs="?", default="", help="text to search")
    wiki_record_search.add_argument("--limit", type=int, default=20)
    add_wiki_options(wiki_record_search)
    wiki_lineage = subparsers.add_parser("wiki-lineage", help="trace one typed record upstream and downstream")
    wiki_lineage.add_argument("record_id", help="stable record ID")
    wiki_lineage.add_argument("--direction", choices=("upstream", "downstream", "both"), default="both")
    wiki_lineage.add_argument("--registry-root", type=Path, help="optional thermophysical-data-registry root for link checks")
    add_wiki_options(wiki_lineage)
    wiki_record_template = subparsers.add_parser(
        "wiki-record-template",
        help="print a read-only template for a new typed knowledge record",
    )
    wiki_record_template.add_argument(
        "record_type",
        choices=(
            "paper_brief",
            "claim",
            "equation",
            "dataset_reference",
            "parameter_reference",
            "correlation_reference",
            "idea",
            "insight",
            "workflow",
            "implementation_reference",
            "validation_run",
        ),
    )
    wiki_record_template.add_argument("--record-id", default="", help="optional type-prefixed stable ID")
    wiki_record_template.add_argument("--title", default="", help="optional human title")
    wiki_record_template.add_argument("--zotero-key", default="", help="optional source Zotero key")
    wiki_record_template.add_argument("--json", action="store_true", help="emit JSON")
    wiki_paper_template = subparsers.add_parser(
        "wiki-paper-template",
        help="print a metadata-only Markdown brief scaffold",
    )
    wiki_paper_template.add_argument("key", help="materialized Zotero item key")
    add_wiki_options(wiki_paper_template)
    wiki_lint = subparsers.add_parser("wiki-lint", help="lint typed records, relations, and provenance links")
    wiki_lint.add_argument("--registry-root", type=Path, help="optional thermophysical-data-registry root for link checks")
    add_wiki_options(wiki_lint)
    wiki_manifest = subparsers.add_parser("wiki-manifest", help="read one project data manifest or list all manifests")
    wiki_manifest.add_argument("project", nargs="?", help="project id, for example epcsaft-equilibrium")
    add_wiki_options(wiki_manifest)
    wiki_manifest_lint = subparsers.add_parser("wiki-manifest-lint", help="lint project manifests and registry paths")
    wiki_manifest_lint.add_argument("--registry-root", type=Path, help="optional thermophysical-data-registry root")
    add_wiki_options(wiki_manifest_lint)
    wiki_health = subparsers.add_parser(
        "wiki-health",
        help="report dependency health and a read-only review queue",
    )
    wiki_health.add_argument(
        "--stale-source",
        dest="stale_sources",
        action="append",
        default=[],
        help="Zotero key whose source-derived records need review; repeatable",
    )
    wiki_health.add_argument(
        "--registry-changed",
        dest="changed_registry_ids",
        action="append",
        default=[],
        help="registry ID whose linked records need review; repeatable",
    )
    wiki_health.add_argument(
        "--record",
        dest="record_ids",
        action="append",
        default=[],
        help="typed record ID that needs review; repeatable",
    )
    wiki_health.add_argument("--limit", type=int, default=100)
    wiki_health.add_argument("--registry-root", type=Path, help="optional thermophysical-data-registry root")
    add_wiki_options(wiki_health)
    wiki_coverage = subparsers.add_parser(
        "wiki-coverage",
        help="report full-corpus curation coverage and bounded gaps",
    )
    wiki_coverage.add_argument("--limit", type=int, default=20)
    add_wiki_options(wiki_coverage)
    wiki_release = subparsers.add_parser(
        "wiki-release",
        help="plan or write a local reproducibility manifest",
    )
    wiki_release.add_argument("--apply", action="store_true", help="write wiki/release-manifest.json")
    wiki_release.add_argument("--registry-root", type=Path, help="optional thermophysical-data-registry root")
    add_wiki_options(wiki_release)
    wiki_triage = subparsers.add_parser(
        "wiki-triage",
        help="read the generated all-source relevance and curation queues",
    )
    wiki_triage.add_argument("--status", help="filter by curation status")
    wiki_triage.add_argument("--project", help="filter by project view")
    wiki_triage.add_argument(
        "--queue",
        choices=(
            "needs_classification",
            "classification_review",
            "unbriefed_relevant",
            "evidence_ready",
            "brief_scaffolded",
            "briefed",
            "discovered",
        ),
        help="return one generated work queue",
    )
    wiki_triage.add_argument("--domain", help="filter by explicit or suggested domain")
    wiki_triage.add_argument(
        "--thread",
        dest="research_thread",
        help="filter by explicit or suggested research thread",
    )
    wiki_triage.add_argument(
        "--relevance",
        choices=("candidate", "relevant", "uncertain", "not_relevant"),
        help="filter by explicit classification relevance",
    )
    wiki_triage.add_argument(
        "--classification-state",
        choices=("unassigned", "proposed", "accepted", "rejected"),
        help="filter by explicit classification state",
    )
    wiki_triage.add_argument(
        "--assigned-only",
        action="store_true",
        help="when filtering by domain/thread, exclude metadata suggestions",
    )
    wiki_triage.add_argument("--limit", type=int, default=20)
    add_wiki_options(wiki_triage)
    wiki_classify = subparsers.add_parser(
        "wiki-classify",
        help="plan or record one explicit source domain/thread classification",
    )
    wiki_classify.add_argument("key", help="materialized Zotero item key")
    wiki_classify.add_argument(
        "--relevance",
        required=True,
        choices=("candidate", "relevant", "uncertain", "not_relevant"),
    )
    wiki_classify.add_argument(
        "--domain",
        dest="domains",
        action="append",
        default=[],
        help="explicit domain id; repeat for multiple domains",
    )
    wiki_classify.add_argument(
        "--thread",
        dest="research_threads",
        action="append",
        default=[],
        help="explicit research-thread id; repeat for multiple threads",
    )
    wiki_classify.add_argument("--reason", required=True, help="why this classification is being recorded")
    wiki_classify.add_argument(
        "--state",
        choices=("proposed", "accepted", "rejected"),
        default="proposed",
    )
    wiki_classify.add_argument("--reviewer", default="", help="human or agent reviewer label")
    wiki_classify.add_argument("--reviewed-at", default="", help="review date or revision label")
    wiki_classify.add_argument(
        "--apply",
        action="store_true",
        help="write the curated assignment and rebuild triage",
    )
    add_wiki_options(wiki_classify)
    wiki_verify = subparsers.add_parser("wiki-verify", help="verify materialized wiki artifacts")
    add_wiki_options(wiki_verify)
    wiki_stale = subparsers.add_parser("wiki-stale", help="compare the wiki with a fresh Zotero read")
    add_wiki_options(wiki_stale)
    project_register = subparsers.add_parser(
        "project-register",
        help="bind a project slug to its Zotero collection under the project root collection",
    )
    project_register.add_argument("--slug", required=True, help="stable project slug, e.g. mea-thermodynamics")
    target = project_register.add_mutually_exclusive_group(required=True)
    target.add_argument("--collection", help="existing Zotero collection key inside the root collection")
    target.add_argument("--create", metavar="NAME", help="create a new collection directly under the root")
    project_register.add_argument("--repository", default="", help="absolute path of the project repository")
    project_register.add_argument("--root", help="set the top-level project collection key")
    project_register.add_argument("--apply", action="store_true", help="write the registry and sync the page")
    project_list = subparsers.add_parser("project-list", help="list registered project libraries")
    project_sync = subparsers.add_parser(
        "project-sync",
        help="render registered project pages from their live Zotero collection trees",
    )
    project_sync.add_argument("--slug", help="sync one project (default: all)")
    project_sync.add_argument("--apply", action="store_true", help="write changed pages")
    project_organize = subparsers.add_parser(
        "project-organize",
        help="preview or apply a collection reorganization inside one project's Zotero tree",
    )
    project_organize.add_argument("plan", type=Path, help='JSON: {"project": slug, "operations": [...]}')
    project_organize.add_argument("--apply", action="store_true", help="apply through the Zotero add-on, then sync")
    for command in (project_register, project_list, project_sync, project_organize):
        add_wiki_options(command)
        command.add_argument(
            "--registry", type=Path, default=None,
            help="project registry path (the Zotero add-on always reads the default one)",
        )
    args = parser.parse_args()
    if args.command == "acquire":
        try:
            payload = acquire(args.identifier, collection=args.collection, dry_run=args.dry_run, route=args.route)
        except (AcquireStop, OSError, ValueError) as exc:
            payload = {"ok": False, "stop_reason": str(exc)}
        emit_json(payload)
        return 0 if payload.get("ok") else 1
    if args.command in {
        "zotero-search",
        "zotero-children",
        "zotero-attachment-path",
        "mathpix-convert",
        "zotero-attach-companion",
    }:
        try:
            if args.command == "zotero-search":
                payload = search_sources(args.query, limit=args.limit)
            elif args.command == "zotero-children":
                payload = source_children(args.parent_key)
            elif args.command == "zotero-attachment-path":
                payload = attachment_path(args.attachment_key)
            elif args.command == "mathpix-convert":
                payload = mathpix_conversion(
                    args.parent_key,
                    args.pdf_key,
                    load_config(args.config),
                    destination=args.out,
                    apply=args.apply,
                )
            else:
                payload = ZoteroLocalAPIWriter(key_path=args.key_file).linked_attachment(
                    args.parent_key,
                    args.companion,
                    apply=args.apply,
                )
        except (ConfigError, LocalAPIError, MathpixOperationError, WriterError, OSError, ValueError) as exc:
            parser.error(str(exc))
        emit_json(payload)
        return 0 if payload.get("ok", True) else 1
    if args.command in {"doctor", "init", "bibliography-export", "corpus-migrate"}:
        try:
            if args.command == "init":
                existing = None
                preview_sha256 = None
                if args.config.is_file():
                    existing, original = _read_config_snapshot(args.config)
                    preview_sha256 = hashlib.sha256(original).hexdigest()
                config = proposed_config(
                    corpus_root=args.corpus_root,
                    existing=existing,
                    mathpix_library_consent=args.mathpix_consent,
                )
                if existing == config:
                    payload = config_payload(config, args.config, mode="unchanged")
                elif args.apply:
                    if existing is None and (args.corpus_root is None or args.mathpix_consent is None):
                        raise ConfigError(
                            "fresh init --apply requires --corpus-root and an explicit "
                            "--mathpix-consent or --no-mathpix-consent choice"
                        )
                    if existing is not None and args.preview_sha256 is None:
                        raise ConfigError(
                            "init --apply for a changed existing configuration requires "
                            "--preview-sha256 from the dry-run"
                        )
                    payload = write_config(
                        config, args.config, expected_sha256=args.preview_sha256
                    )
                else:
                    payload = config_payload(config, args.config, mode="dry-run")
                if existing is not None:
                    current = config_payload(existing, args.config, mode="current")
                    payload["changes"] = {
                        key: {"current": current[key], "proposed": payload[key]}
                        for key in current
                        if key not in {"ok", "mode"} and current[key] != payload[key]
                    }
                    if existing != config and not args.apply:
                        payload["preview_sha256"] = preview_sha256
            else:
                configuration_error = ""
                config = None
                if args.command == "doctor":
                    try:
                        config = load_config(args.config)
                    except (ConfigError, OSError, ValueError) as exc:
                        configuration_error = str(exc)
                else:
                    config = load_config(args.config)
                if args.command == "corpus-migrate":
                    payload = migrate_corpus(args.source_root, config, apply=args.apply)
                elif args.command == "bibliography-export":
                    payload = (
                        configure_export(config.bibliography_export)
                        if args.apply
                        else export_plan(config.bibliography_export)
                    )
                else:
                    zotero_ok = False
                    zotero_error = ""
                    try:
                        ZoteroLocalAPI().get("/api/users/0/items", {"limit": 1})
                        zotero_ok = True
                    except LocalAPIError as exc:
                        zotero_error = str(exc)
                    bbt_ok = False
                    bbt_error = ""
                    bbt_version: dict[str, object] = {}
                    try:
                        bbt_version = BetterBibTeXClient().ready()
                        bbt_ok = True
                    except BetterBibTeXError as exc:
                        bbt_error = str(exc)
                    payload = doctor_payload(
                        args.config,
                        project_libraries=_project_doctor(config, zotero_ok),
                        config=config,
                        configuration_error=configuration_error,
                        zotero={"ok": zotero_ok, "error": zotero_error},
                        better_bibtex={"ok": bbt_ok, "error": bbt_error, **bbt_version},
                        mathpix={"mpx_on_path": shutil.which("mpx") is not None},
                    )
                    payload["acquisition"] = {"tokens": configured_tokens(), "connector": connector_status(),
                                              "contract": "ZOTERO_ACQUISITION.md"}
        except (ConfigError, CorpusMigrationError, BetterBibTeXError, OSError, ValueError) as exc:
            parser.error(str(exc))
        emit_json(payload)
        return 0 if payload.get("ok", True) else 1
    if hasattr(args, "wiki_root") and args.wiki_root is None:
        try:
            args.wiki_root = load_config().wiki_root
        except ConfigError as exc:
            parser.error(str(exc))
    if args.command.startswith("project-"):
        try:
            payload = _project_command(args)
        except (ProjectError, LocalAPIError, PluginClientError, OSError, ValueError) as exc:
            parser.error(str(exc))
        emit_json(payload)
        return 0 if payload.get("ok", True) else 1
    if args.command in {
        "schema-validate",
        "data-query",
        "data-search",
        "data-register",
        "data-select",
        "registry-migrate",
    }:
        try:
            if args.command == "schema-validate":
                payload = validate_catalog(args.data, args.schema, args.target_class)
            elif args.command == "data-query":
                payload = query_table(args.table, args.sql, args.limit)
            elif args.command == "data-search":
                registry_root = args.registry_root
                if registry_root is None:
                    registry_root = (
                        load_config().data_root
                        / "domains"
                        / "thermophysical"
                        / "source"
                        / "registry"
                    )
                payload = search_registry(
                    registry_root,
                    query=args.query,
                    limit=args.limit,
                )
            elif args.command == "data-register":
                payload = register_package(
                    args.package,
                    registry_root=args.registry_root,
                    apply=args.apply,
                    supersede=args.supersede,
                )
            elif args.command == "data-select":
                registry_root = args.registry_root
                if registry_root is None:
                    registry_root = (
                        load_config().data_root
                        / "domains"
                        / "thermophysical"
                        / "source"
                        / "registry"
                    )
                payload = select_resource(
                    registry_root,
                    args.record_id,
                    args.analysis,
                    resource=args.resource,
                    version=args.version,
                    apply=args.apply,
                )
            else:
                payload = build_registry_pack(
                    args.registry_root, args.companion_root, apply=args.apply
                )
        except (ScientificDataError, RegistryMigrationError, OSError, ValueError) as exc:
            parser.error(str(exc))
        emit_json(payload)
        return 0 if payload.get("ok", True) else 1
    if args.command == "audit":
        try:
            payload = audit_payload(ZoteroLocalAPI())
        except LocalAPIError as exc:
            parser.error(str(exc))
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for key, value in payload.items():
                print(f"{key}: {value}")
        return 0
    if args.command in {"plugin-status", "plugin-tag-cleanup", "plugin-searches"}:
        try:
            client = ZoteroPluginClient()
            if args.command == "plugin-status":
                payload = client.status()
            elif args.command == "plugin-tag-cleanup":
                payload = client.tag_cleanup(apply=args.apply)
            else:
                payload = client.saved_searches(apply=args.apply)
        except PluginClientError as exc:
            parser.error(str(exc))
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.command in {"local-status", "local-tag-cleanup", "local-searches"}:
        try:
            writer = ZoteroLocalAPIWriter(key_path=args.key_file)
            if args.command == "local-status":
                payload = writer.status()
            elif args.command == "local-tag-cleanup":
                payload = writer.tag_cleanup(apply=args.apply)
            else:
                payload = writer.saved_searches(apply=args.apply)
        except WriterError as exc:
            parser.error(str(exc))
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.command in {
        "wiki-sync",
        "wiki-refresh",
        "wiki-maintain",
        "wiki-index",
        "wiki-search",
        "wiki-source",
        "wiki-evidence",
        "wiki-evidence-sync",
        "wiki-context",
        "wiki-record",
        "wiki-record-search",
        "wiki-record-template",
        "wiki-paper-template",
        "wiki-lineage",
        "wiki-lint",
        "wiki-manifest",
        "wiki-manifest-lint",
        "wiki-health",
        "wiki-coverage",
        "wiki-release",
        "wiki-triage",
        "wiki-classify",
        "wiki-verify",
        "wiki-stale",
    }:
        try:
            if args.command in {"wiki-sync", "wiki-refresh"}:
                snapshot = WikiSnapshot.from_api(ZoteroLocalAPI(), project_collections(load_registry()))
                payload = materialize_snapshot(snapshot, args.wiki_root, apply=args.apply)
                if args.command == "wiki-refresh":
                    payload["refresh_scope"] = "generated_source_layer_only"
                    payload["zotero_mutation"] = False
            elif args.command == "wiki-maintain":
                payload = maintain_wiki(
                    args.wiki_root,
                    api=ZoteroLocalAPI(),
                    apply=args.apply,
                    registry=load_registry(),
                )
            elif args.command == "wiki-index":
                if args.apply:
                    payload = index_wiki(args.wiki_root)
                else:
                    source_count = len(list((args.wiki_root / "sources").glob("*/record.json")))
                    payload = {
                        "mode": "dry-run",
                        "wiki_root": str(args.wiki_root),
                        "documents": source_count,
                        "would_write": str(args.wiki_root / "index.sqlite"),
                    }
            elif args.command == "wiki-search":
                payload = search_wiki(
                    args.wiki_root,
                    query=args.query,
                    project=args.project,
                    limit=args.limit,
                )
            elif args.command == "wiki-source":
                payload = source_record(args.wiki_root, args.key)
            elif args.command == "wiki-evidence":
                payload = evidence_passages(
                    args.wiki_root,
                    args.key,
                    query=args.query,
                    limit=args.limit,
                    context_lines=args.context_lines,
                )
            elif args.command == "wiki-evidence-sync":
                payload = sync_evidence(
                    args.wiki_root,
                    api=ZoteroLocalAPI(),
                    keys=args.keys,
                    apply=args.apply,
                )
            elif args.command == "wiki-context":
                if args.global_scope:
                    payload = global_context(
                        args.wiki_root,
                        query=args.query,
                        limit=args.limit,
                        registry_root=args.registry_root,
                        data_root=args.wiki_root.parent / "data",
                        api=ZoteroLocalAPI(),
                    )
                elif args.project:
                    payload = context_pack(
                        args.wiki_root,
                        project=args.project,
                        query=args.query,
                        limit=args.limit,
                        registry_root=args.registry_root,
                        data_root=args.wiki_root.parent / "data",
                        api=ZoteroLocalAPI(),
                    )
                else:
                    parser.error("wiki-context requires a project or --global")
            elif args.command == "wiki-record":
                payload = record_lookup(args.wiki_root, args.record_id)
                payload.pop("_path", None)
            elif args.command == "wiki-record-search":
                payload = {
                    "query": args.query,
                    "records": search_records(args.wiki_root, query=args.query, limit=args.limit),
                    "read_only": True,
                }
            elif args.command == "wiki-record-template":
                payload = record_template(
                    args.record_type,
                    record_id=args.record_id,
                    title=args.title,
                    zotero_key=args.zotero_key,
                )
            elif args.command == "wiki-paper-template":
                payload = paper_brief_template(args.wiki_root, args.key)
            elif args.command == "wiki-lineage":
                payload = lineage(
                    args.wiki_root,
                    args.record_id,
                    direction=args.direction,
                    registry_root=args.registry_root,
                )
            elif args.command == "wiki-lint":
                payload = lint_records(args.wiki_root, registry_root=args.registry_root)
            elif args.command == "wiki-manifest":
                if args.project:
                    payload = manifest_lookup(args.wiki_root, args.project)
                    payload.pop("_path", None)
                else:
                    payload = {
                        "manifests": [
                            {key: value for key, value in manifest.items() if key != "_path"}
                            for manifest in load_manifests(args.wiki_root)
                        ],
                        "read_only": True,
                    }
            elif args.command == "wiki-manifest-lint":
                payload = lint_manifests(args.wiki_root, registry_root=args.registry_root)
            elif args.command == "wiki-health":
                payload = health_report(
                    args.wiki_root,
                    stale_source_keys=args.stale_sources,
                    changed_registry_ids=args.changed_registry_ids,
                    record_ids=args.record_ids,
                    registry_root=args.registry_root,
                    limit=args.limit,
                )
            elif args.command == "wiki-coverage":
                payload = coverage_report(args.wiki_root, limit=args.limit)
            elif args.command == "wiki-release":
                payload = release_plan(
                    args.wiki_root,
                    registry_root=args.registry_root,
                    apply=args.apply,
                )
            elif args.command == "wiki-triage":
                payload = triage_wiki(
                    args.wiki_root,
                    status=args.status,
                    project=args.project,
                    queue=args.queue,
                    domain=args.domain,
                    research_thread=args.research_thread,
                    relevance=args.relevance,
                    classification_state=args.classification_state,
                    assigned_only=args.assigned_only,
                    limit=args.limit,
                )
            elif args.command == "wiki-classify":
                payload = classify_source(
                    args.wiki_root,
                    args.key,
                    relevance=args.relevance,
                    domains=args.domains,
                    research_threads=args.research_threads,
                    reason=args.reason,
                    state=args.state,
                    reviewer=args.reviewer,
                    reviewed_at=args.reviewed_at,
                    apply=args.apply,
                )
            elif args.command == "wiki-verify":
                payload = verify_wiki(args.wiki_root)
            else:
                payload = stale_report(args.wiki_root, ZoteroLocalAPI())
        except (
            LocalAPIError,
            ProjectError,
            WikiError,
            EvidenceSyncError,
            RecordError,
            ManifestError,
            ReleaseError,
            CoverageError,
            ValueError,
        ) as exc:
            parser.error(str(exc))
        emit_json(payload)
        if args.command in {"wiki-maintain", "wiki-verify", "wiki-lint", "wiki-manifest-lint", "wiki-health", "wiki-coverage"} and isinstance(payload, dict) and not payload.get("ok", False):
            return 1
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
