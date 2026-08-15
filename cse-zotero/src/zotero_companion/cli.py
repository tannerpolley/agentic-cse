"""Command-line entry point for Zotero Companion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from .better_bibtex import BetterBibTeXClient, BetterBibTeXError, configure_export, export_plan
from .config import (
    CAPABILITIES,
    PROTOCOL_VERSION,
    ConfigError,
    config_payload,
    default_config_path,
    load_config,
    proposed_config,
    write_config,
)
from .corpus_migration import CorpusMigrationError, migrate_corpus
from .coverage import CoverageError, coverage_report
from .evidence_sync import EvidenceSyncError, sync_evidence
from .local_api import LocalAPIError, ZoteroLocalAPI
from .manifests import ManifestError, lint_manifests, load_manifests, manifest_lookup
from .plugin_client import PluginClientError, ZoteroPluginClient
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
from .report import audit_payload
from .scientific_data import ScientificDataError, query_table, validate_catalog
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="zotero-companion")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="report installed protocol and capability readiness")
    doctor.add_argument("--config", type=Path, default=default_config_path())
    doctor.add_argument("--json", action="store_true")
    initialize = subparsers.add_parser("init", help="plan or initialize user-owned Companion configuration")
    initialize.add_argument("--config", type=Path, default=default_config_path())
    initialize.add_argument("--corpus-root", type=Path)
    initialize.add_argument("--apply", action="store_true")
    initialize.add_argument("--json", action="store_true")
    bibliography = subparsers.add_parser(
        "bibliography-export", help="plan or refresh the canonical Better BibTeX library export"
    )
    bibliography.add_argument("--config", type=Path, default=default_config_path())
    bibliography.add_argument("--apply", action="store_true")
    bibliography.add_argument("--json", action="store_true")
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
    schema_validate.add_argument("--schema", type=Path, default=Path("schema/companion.yaml"))
    schema_validate.add_argument("--class", dest="target_class", default="CompanionCatalog")
    schema_validate.add_argument("--json", action="store_true")
    data_query = subparsers.add_parser(
        "data-query", help="run a bounded read-only DuckDB query over a retained table"
    )
    data_query.add_argument("table", type=Path)
    data_query.add_argument("--sql", default="SELECT * FROM records")
    data_query.add_argument("--limit", type=int, default=100)
    data_query.add_argument("--json", action="store_true")
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
    args = parser.parse_args()
    if args.command in {"doctor", "init", "bibliography-export", "corpus-migrate"}:
        try:
            if args.command == "init":
                config = proposed_config(corpus_root=args.corpus_root)
                payload = (
                    write_config(config, args.config)
                    if args.apply
                    else config_payload(config, args.config, mode="dry-run")
                )
            else:
                config = load_config(args.config, allow_proposed=args.command == "doctor")
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
                    payload = {
                        **config_payload(config, args.config, mode="read-only"),
                        "protocol_version": PROTOCOL_VERSION,
                        "capabilities": list(CAPABILITIES),
                        "zotero": {"ok": zotero_ok, "error": zotero_error},
                        "better_bibtex": {"ok": bbt_ok, "error": bbt_error, **bbt_version},
                        "mathpix": {"mpx_on_path": shutil.which("mpx") is not None},
                        "configuration_exists": Path(args.config).is_file(),
                    }
                    payload["ok"] = zotero_ok and bbt_ok and Path(args.config).is_file()
        except (ConfigError, CorpusMigrationError, BetterBibTeXError, OSError, ValueError) as exc:
            parser.error(str(exc))
        emit_json(payload)
        return 0 if payload.get("ok", True) else 1
    if hasattr(args, "wiki_root") and args.wiki_root is None:
        try:
            args.wiki_root = load_config().wiki_root
        except ConfigError as exc:
            parser.error(str(exc))
    if args.command in {"schema-validate", "data-query", "registry-migrate"}:
        try:
            if args.command == "schema-validate":
                payload = validate_catalog(args.data, args.schema, args.target_class)
            elif args.command == "data-query":
                payload = query_table(args.table, args.sql, args.limit)
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
                snapshot = WikiSnapshot.from_api(ZoteroLocalAPI())
                payload = materialize_snapshot(snapshot, args.wiki_root, apply=args.apply)
                if args.command == "wiki-refresh":
                    payload["refresh_scope"] = "generated_source_layer_only"
                    payload["zotero_mutation"] = False
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
                        api=ZoteroLocalAPI(),
                    )
                elif args.project:
                    payload = context_pack(
                        args.wiki_root,
                        project=args.project,
                        query=args.query,
                        limit=args.limit,
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
        if args.command in {"wiki-verify", "wiki-lint", "wiki-manifest-lint", "wiki-health", "wiki-coverage"} and isinstance(payload, dict) and not payload.get("ok", False):
            return 1
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
