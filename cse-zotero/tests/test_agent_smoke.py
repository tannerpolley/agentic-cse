from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from scripts.agent_smoke import run_smoke
from corpus_paths import WIKI_ROOT


def test_public_cli_agent_contract_is_read_only():
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
