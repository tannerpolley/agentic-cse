from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/convert_with_mpx.py"


def run_wrapper(source: Path, destination: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--out", str(destination), *extra],
        check=False,
        capture_output=True,
        text=True,
    )


def test_pdf_conversion_requires_companion_check(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    destination = tmp_path / "converted.mmd"
    source.write_bytes(b"%PDF-1.4\n")

    result = run_wrapper(source, destination)

    assert result.returncode == 1
    assert "confirmed-no-companion" in result.stderr
    assert not destination.exists()


def test_pdf_conversion_refuses_adjacent_same_stem_companion(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    destination = tmp_path / "converted.mmd"
    source.write_bytes(b"%PDF-1.4\n")
    source.with_suffix(".md").write_text("# Existing companion\n", encoding="utf-8")

    result = run_wrapper(source, destination, "--confirmed-no-companion")

    assert result.returncode == 1
    assert "existing Markdown companion" in result.stderr
    assert not destination.exists()
