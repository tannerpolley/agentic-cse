import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _benchmark_module():
    path = REPO_ROOT / "scripts/benchmark_wiki.py"
    spec = importlib.util.spec_from_file_location("zotero_wiki_benchmark", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_agent_tasks_pass_without_pdf_reads():
    result = _benchmark_module().run_benchmark(
        REPO_ROOT / "wiki",
        REPO_ROOT / "benchmarks/agent_tasks.json",
    )

    assert result["summary"]["recall"] == 1.0
    assert result["summary"]["full_pdf_reads"] == 0
    assert result["summary"]["all_read_only"] is True
    assert result["decision"]["additional_retrieval_infrastructure_justified"] is False
