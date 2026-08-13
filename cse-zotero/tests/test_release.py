from pathlib import Path

from zotero_companion.release import RELEASE_FILENAME, release_plan


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_ROOT = REPO_ROOT / "data/domains/thermophysical/source/registry"


def test_release_dry_run_is_local_and_reports_reproducibility_state():
    root = REPO_ROOT / "wiki"
    release_path = root / RELEASE_FILENAME
    before = release_path.read_bytes() if release_path.exists() else None
    output = release_plan(
        root,
        registry_root=REGISTRY_ROOT,
    )

    assert output["mode"] == "dry-run"
    assert output["read_only"] is True
    assert output["release"]["reproducibility"]["zotero_mutation"] is False
    assert output["release"]["reproducibility"]["pdf_conversion"] is False
    assert output["release"]["scope"] == "zotero-companion"
    assert output["release"]["repository"]["root"] == "."
    assert "path" not in output["release"]["repository"]
    assert output["would_write"] == RELEASE_FILENAME
    assert "wiki/evidence/28NPJ5H6/Hamer1972.md" in output["release"]["artifacts"]
    assert (release_path.read_bytes() if release_path.exists() else None) == before


def test_release_apply_writes_only_the_explicit_local_manifest(tmp_path):
    root = tmp_path / "wiki"
    root.mkdir()

    output = release_plan(root, apply=True)

    assert output["mode"] == "apply"
    assert output["written"] is True
    assert (root / RELEASE_FILENAME).exists()
    assert output["path"] == RELEASE_FILENAME
    assert output["zotero_mutation"] is False
