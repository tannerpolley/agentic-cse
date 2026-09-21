import json
from pathlib import Path

import pytest

from zotero_companion.manifests import lint_manifests, manifest_lookup


@pytest.mark.live
def test_project_manifests_pin_records_and_registry_paths():
    from corpus_paths import REGISTRY_ROOT, WIKI_ROOT

    root = WIKI_ROOT
    checked = lint_manifests(
        root,
        registry_root=REGISTRY_ROOT,
    )

    assert checked["ok"] is True
    assert checked["manifest_count"] == 3
    assert checked["projects"] == ["epcsaft-equilibrium", "lithium-extraction", "mea-thermodynamics"]
    manifest = manifest_lookup(root, "epcsaft-equilibrium")
    assert "validation:figiel-2025-eos-reproduction" in manifest["validation_runs"]
    assert manifest["registry"]["revision"] == "30e57a7442741df2c278191b999996e3f44ceff1"


def test_manifest_lint_rejects_unknown_record_and_bad_registry_path(tmp_path):
    root = tmp_path / "wiki"
    manifest_dir = root / "manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "broken.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": "broken-project",
                "title": "Broken",
                "status": "active",
                "record_ids": ["equation:missing"],
                "registry": {
                    "name": "thermophysical-data-registry",
                    "repository": "../registry",
                    "revision": "working-tree",
                },
                "registry_refs": [{"path": "missing.json"}],
                "validation_runs": ["validation:missing"],
            }
        ),
        encoding="utf-8",
    )

    checked = lint_manifests(root, registry_root=tmp_path / "registry")

    assert checked["ok"] is False
    assert any("unresolved record_id" in error for error in checked["errors"])
    assert any("missing registry reference path" in error for error in checked["errors"])
    assert any("unresolved validation run" in error for error in checked["errors"])


def test_project_owned_manifest_can_omit_registry_but_undeclared_data_cannot(tmp_path):
    root = tmp_path / "wiki"
    manifest_dir = root / "manifests"
    manifest_dir.mkdir(parents=True)
    data_path = tmp_path / "data" / "project-owned" / "observations.csv"
    data_path.parent.mkdir(parents=True)
    data_path.write_text("value,value_unit\n1,kg/m3\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "project_id": "project-owned",
        "title": "Project-owned data",
        "status": "active",
        "record_ids": [],
        "data_authority": "project",
        "datasets": [{"path": "data/project-owned/observations.csv"}],
        "validation_runs": [],
    }
    path = manifest_dir / "project-owned.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    checked = lint_manifests(root)

    assert checked["ok"] is True

    manifest["data_authority"] = "registry"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    contradictory = lint_manifests(root)
    assert contradictory["ok"] is False
    assert any("registry must be an object" in error for error in contradictory["errors"])

    manifest.pop("data_authority")
    manifest.pop("datasets")
    path.write_text(json.dumps(manifest), encoding="utf-8")
    rejected = lint_manifests(root)

    assert rejected["ok"] is False
    assert any("registry must be an object" in error for error in rejected["errors"])


def test_project_manifest_json_schema_keeps_registry_optional_only_for_project_data():
    from jsonschema import Draft202012Validator

    schema = json.loads(
        (Path(__file__).parents[1] / "src/zotero_companion/schemas/json/project-manifest.schema.json").read_text()
    )
    validator = Draft202012Validator(schema)
    base = {
        "schema_version": 1,
        "project_id": "schema-project",
        "title": "Schema project",
        "status": "active",
        "record_ids": [],
    }

    assert validator.is_valid({**base, "data_authority": "project"})
    assert validator.is_valid({**base, "registry": {"name": "r", "repository": "r", "revision": "1"}})
    assert not validator.is_valid(base)
    assert not validator.is_valid({**base, "data_authority": "registry"})


def test_project_manifest_lint_verifies_declared_data_hash(tmp_path):
    import hashlib

    root = tmp_path / "wiki"
    manifest_dir = root / "manifests"
    manifest_dir.mkdir(parents=True)
    data_path = tmp_path / "data.csv"
    data_path.write_text("value\n1\n", encoding="utf-8")
    manifest_dir.joinpath("project.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": "hashed-project",
                "title": "Hashed project",
                "status": "active",
                "record_ids": [],
                "data_authority": "project",
                "datasets": [{
                    "path": "data.csv",
                    "sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
                }],
                "validation_runs": [],
            }
        ),
        encoding="utf-8",
    )

    assert lint_manifests(root)["ok"] is True
    data_path.write_text("value\n2\n", encoding="utf-8")
    assert lint_manifests(root)["ok"] is False
