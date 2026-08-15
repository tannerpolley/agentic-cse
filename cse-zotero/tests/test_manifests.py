import json
from pathlib import Path

from zotero_companion.manifests import lint_manifests, manifest_lookup
from corpus_paths import REGISTRY_ROOT, WIKI_ROOT


def test_project_manifests_pin_records_and_registry_paths():
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
