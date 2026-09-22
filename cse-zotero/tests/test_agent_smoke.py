import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from scripts.agent_smoke import run_smoke


@pytest.mark.live
def test_public_cli_agent_contract_is_read_only():
    from corpus_paths import WIKI_ROOT

    result = run_smoke(
        WIKI_ROOT,
        REPO_ROOT / "benchmarks/agent_tasks.json",
        task_limit=1,
    )

    assert result["summary"] == {
        "all_read_only": True,
        "full_pdf_reads": 0,
        "passed_count": 1,
        "repository_writes": False,
        "task_count": 1,
        "zotero_mutation": False,
    }


def test_installed_cli_resolves_packaged_schema_outside_checkout(tmp_path):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    for alias in ("cse-zotero", "zotero-companion"):
        completed = subprocess.run(
            [
                "uv",
                "run",
                "--isolated",
                "--with",
                str(REPO_ROOT),
                "--directory",
                str(tmp_path),
                alias,
                "schema-validate",
                str(REPO_ROOT / "examples/core-records.yaml"),
                "--json",
            ],
            cwd=tmp_path,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        payload = json.loads(completed.stdout)
        assert payload["ok"] is True
        assert payload["schema"] == "zotero_companion/schemas/linkml/companion.yaml"

    assets = subprocess.run(
        [
            "uv",
            "run",
            "--isolated",
            "--with",
            str(REPO_ROOT),
            "--directory",
            str(tmp_path),
            "python",
            "-c",
            (
                "from importlib.resources import files; "
                "assert files('zotero_companion').joinpath("
                "'schemas/json/project-manifest.schema.json').is_file()"
            ),
        ],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert assets.returncode == 0, assets.stderr



def test_installed_cli_queries_and_restores_registered_fixture_outside_checkout(tmp_path):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    corpus = tmp_path / "corpus"
    package = corpus / "data/registered-mea-density"
    shutil.copytree(REPO_ROOT / "examples/data-register/package", package)
    registry = corpus / "source/registry"
    registry.mkdir(parents=True)
    installed_cli = [
        "uv",
        "run",
        "--isolated",
        "--with",
        str(REPO_ROOT),
        "--directory",
        str(tmp_path),
        "cse-zotero",
    ]

    def run_cli(*arguments):
        completed = subprocess.run(
            [*installed_cli, *arguments],
            cwd=tmp_path,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        return json.loads(completed.stdout)

    registered = run_cli(
        "data-register",
        str(package),
        "--registry-root",
        str(registry),
        "--apply",
        "--json",
    )
    assert registered["mode"] == "apply"

    discovered = run_cli(
        "data-search",
        "MEA density",
        "--registry-root",
        str(registry),
        "--json",
    )
    assert discovered["count"] == 1
    result = discovered["results"][0]
    assert result["provenance"]["zotero_key"] == "ABCD1234"
    assert result["provenance"]["locator"] == {
        "kind": "table",
        "value": "Table 2, row 1",
    }
    dataset = Path(result["resources"][0]["path"])
    queried = run_cli(
        "data-query",
        str(dataset),
        "--sql",
        "SELECT value, value_unit FROM records",
        "--json",
    )
    assert queried["rows"] == [{"value": 1010.2, "value_unit": "kg/m3"}]

    record = corpus / "wiki/projects/registered-mea-density.md"
    record.parent.mkdir(parents=True)
    record.write_text(
        "# Registered MEA density\n\n"
        "Dataset ds:registered-mea-density; Zotero item ABCD1234, "
        "locator Table 2, row 1; observation 1010.2 kg/m3.\n",
        encoding="utf-8",
    )
    sources = (record, dataset)
    expected_hashes = {
        str(source.relative_to(corpus)): hashlib.sha256(source.read_bytes()).hexdigest()
        for source in sources
    }
    recovery = tmp_path / "recovery"
    for source in sources:
        destination = recovery / source.relative_to(corpus)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    restored_hashes = {
        relative: hashlib.sha256((recovery / relative).read_bytes()).hexdigest()
        for relative in expected_hashes
    }
    assert restored_hashes == expected_hashes
    restored_query = run_cli(
        "data-query",
        str(recovery / "data/registered-mea-density/observations.csv"),
        "--sql",
        "SELECT value, value_unit FROM records",
        "--json",
    )
    assert restored_query["rows"] == queried["rows"]
