import csv
import json
from pathlib import Path
import subprocess

import pytest

from zotero_companion.registry_migration import RegistryMigrationError, build_registry_pack


FIELDS = [
    "candidate_id",
    "source_repository_id",
    "source_path",
    "source_sha256",
    "destination",
    "duplicate_group_size",
    "system_kind",
    "system_id",
    "property_family",
    "record_class",
    "source_status",
    "evidence_label",
    "match_method",
    "zotero_keys",
    "citation_keys",
    "dois",
    "attachment_keys",
    "wiki_evidence_paths",
    "locators",
    "source_labels",
    "blocker_codes",
    "exact_request",
]


def write_queue(path: Path, status: str):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow({"candidate_id": f"candidate:{status}", "source_status": status})


def registry_fixture(root: Path):
    species = root / "data/species/water/species.json"
    species.parent.mkdir(parents=True)
    species.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record_type": "species",
                "species_id": "water",
                "preferred_name": "water",
            }
        )
    )
    migration = root / "docs/migration"
    migration.mkdir(parents=True)
    write_queue(migration / "source-ready-candidates.csv", "source-ready")
    write_queue(migration / "source-blocked-candidates.csv", "source-blocked")
    (root / "CONTEXT.md").write_text("# Registry context\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"],
        cwd=root,
        check=True,
    )


def test_registry_pack_preserves_source_and_reports_quarantine(tmp_path):
    registry = tmp_path / "registry"
    companion = tmp_path / "companion"
    registry_fixture(registry)

    preview = build_registry_pack(registry, companion, apply=False)
    result = build_registry_pack(registry, companion, apply=True)
    destination = companion / "data/domains/thermophysical"

    assert preview["source_files"] == 4
    assert preview["canonical_records"] == 1
    assert result["source_ready"] == 1
    assert result["quarantined"] == 1
    assert result["source_repository"] == "registry"
    assert result["destination"] == "data/domains/thermophysical"
    assert (destination / "source/registry/data/species/water/species.json").is_file()
    assert (destination / "source/registry/CONTEXT.md").is_file()
    assert (destination / "normalized/registry-records.csv").is_file()
    assert (destination / "quarantine/source-blocked-candidates.csv").is_file()
    with pytest.raises(RegistryMigrationError, match="already exists"):
        build_registry_pack(registry, companion, apply=True)
