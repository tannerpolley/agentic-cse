"""Developer-neutral validation ladder for the complete scientific project."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THREAD_ENV = {
    **os.environ,
    "OPENBLAS_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "MPLBACKEND": "Agg",
}


def run(*command: str) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=THREAD_ENV, check=True)


def quick() -> None:
    run("uv", "run", "ruff", "check", "src", "tests", "scripts", "analyses/heat_verification")
    run("uv", "run", "pytest")
    run("uv", "run", "python", "scripts/check_repository.py")
    run("bash", "scripts/sync_bibliography.sh", "--check")


def confidence() -> None:
    quick()
    run("uv", "run", "python", "analyses/heat_verification/scripts/generate_all.py")
    run("uv", "run", "python", "analyses/heat_verification/scripts/validate_results.py")


def docs() -> None:
    run("bash", "docs/scientific/latex/scripts/build_main.sh")
    scientific_documents = (
        "docs/scientific/formulation.tex",
        "docs/scientific/methods.tex",
        "docs/scientific/evidence.tex",
    )
    with tempfile.TemporaryDirectory(prefix="cse-heat-equation-example-") as temporary:
        for document in scientific_documents:
            run(
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                f"-outdir={temporary}",
                document,
            )
        run(
            "quarto",
            "render",
            "analyses/heat_verification/notebook.qmd",
            "--to",
            "pdf",
            "--no-execute",
            "--output-dir",
            temporary,
        )
        if not (Path(temporary) / "notebook.pdf").is_file():
            raise SystemExit("analysis notebook render did not produce notebook.pdf")


def full() -> None:
    confidence()
    run("uv", "run", "python", "analyses/heat_verification/scripts/render_all.py")
    run("uv", "run", "python", "analyses/heat_verification/scripts/validate_results.py")
    docs()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("quick", "confidence", "docs", "full"))
    mode = parser.parse_args().mode
    {"quick": quick, "confidence": confidence, "docs": docs, "full": full}[mode]()
    print(f"Scientific project validation passed: {mode}")


if __name__ == "__main__":
    main()
