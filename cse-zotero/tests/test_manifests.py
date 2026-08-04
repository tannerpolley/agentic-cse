import json
from pathlib import Path

from zotero_wiki.manifests import lint_manifests, manifest_lookup


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_project_manifests_pin_records_and_registry_paths():
    root = REPO_ROOT / "wiki"
    checked = lint_manifests(
        root,
        registry_root=REPO_ROOT.parent / "thermophysical-data-registry",
    )

    assert checked["ok"] is True
    assert checked["manifest_count"] == 3
    assert checked["projects"] == ["epcsaft-equilibrium", "lithium-extraction", "mea-thermodynamics"]
    manifest = manifest_lookup(root, "epcsaft-equilibrium")
    assert "validation:figiel-2025-eos-reproduction" in manifest["validation_runs"]
    assert manifest["registry"]["revision"] == "working-tree"


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
