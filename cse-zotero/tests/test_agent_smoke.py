import json
import os
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
