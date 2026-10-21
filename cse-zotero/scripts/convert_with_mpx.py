#!/usr/bin/env python3
"""Convert PDFs/images with Mathpix mpx using the signed-in Snip account."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_SOURCE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
SUPPORTED_OUTPUT_FORMATS = {"mmd", "md"}
COMPANION_EXTENSIONS = {".md", ".mmd"}


def parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def same_stem_companions(source: Path) -> list[Path]:
    """Return Markdown companions adjacent to the source, case-insensitively."""
    return sorted(
        candidate
        for candidate in source.parent.iterdir()
        if candidate.is_file()
        and candidate.suffix.lower() in COMPANION_EXTENSIONS
        and candidate.stem.casefold() == source.stem.casefold()
    )


def require_snip_auth() -> None:
    config = parse_dotenv(Path.home() / ".mpx" / "config")
    if os.environ.get("MATHPIX_OCR_API_KEY") or config.get("MATHPIX_OCR_API_KEY"):
        fail("MATHPIX_OCR_API_KEY is present; refusing OCR API-key billing.")
    if not (os.environ.get("MATHPIX_SNIP_AUTH_TOKEN") or config.get("MATHPIX_SNIP_AUTH_TOKEN")):
        fail("Mathpix Snip auth token is missing. Run `mpx login` in a real terminal.")
    if not (os.environ.get("MATHPIX_SNIP_PRICING_AGREE") or config.get("MATHPIX_SNIP_PRICING_AGREE")):
        fail("Mathpix Snip pricing acknowledgement is missing. Run `mpx login` in a real terminal.")


def find_mpx_cli_js() -> Path:
    mpx = shutil.which("mpx.cmd" if os.name == "nt" else "mpx")
    if mpx:
        cli_js = Path(mpx).resolve()
        if cli_js.name == "cli.js" and cli_js.is_file():
            return cli_js

    npm = "npm.cmd" if os.name == "nt" else "npm"
    try:
        result = subprocess.run(
            [npm, "root", "-g"],
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        fail("npm is not available on PATH; install Node.js/npm before using mpx.")
    except subprocess.CalledProcessError as exc:
        fail(f"`npm root -g` failed: {exc.stderr.strip() or exc.stdout.strip()}")

    cli_js = Path(result.stdout.strip()) / "@mathpix" / "mpx-cli" / "bin" / "cli.js"
    if not cli_js.exists():
        fail(
            "@mathpix/mpx-cli is not installed on PATH or in npm's global prefix. "
            "Install it with `npm install -g --prefix \"$HOME/.local\" @mathpix/mpx-cli`."
        )
    return cli_js


def convert(source: Path, destination: Path) -> None:
    node = "node.exe" if os.name == "nt" else "node"
    cli_js = find_mpx_cli_js()
    shim = (
        "const cli = process.argv.pop(); "
        "process.argv.splice(1, 0, 'mpx'); "
        "process.stdout.clearLine = process.stdout.clearLine || function() {}; "
        "process.stdout.cursorTo = process.stdout.cursorTo || function() {}; "
        "require(cli);"
    )
    command = [node, "-e", shim, "--", "convert", str(source), str(destination), str(cli_js)]
    subprocess.run(command, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a PDF/image to Markdown with Mathpix mpx using Snip auth.")
    parser.add_argument("source", type=Path, help="Source PDF/image path.")
    parser.add_argument("--out", type=Path, required=True, help="Destination .mmd or .md path.")
    parser.add_argument("--format", choices=sorted(SUPPORTED_OUTPUT_FORMATS), default="mmd")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing destination file.")
    parser.add_argument(
        "--confirmed-no-companion",
        action="store_true",
        help="Confirm Zotero children were checked and no usable .md/.mmd companion exists.",
    )
    parser.add_argument(
        "--force-reconvert",
        action="store_true",
        help="Explicitly allow reconversion despite a companion; use only for comparison or re-OCR.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = args.source.expanduser().resolve()
    destination = args.out.expanduser().resolve()
    if not source.exists():
        fail(f"source file does not exist: {source}")
    if source.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
        fail(f"unsupported source extension `{source.suffix}`")
    if destination.suffix.lower() != f".{args.format}":
        fail(f"destination suffix must be `.{args.format}` for --format {args.format}: {destination}")
    if destination.exists() and not args.overwrite:
        fail(f"destination already exists; pass --overwrite to replace it: {destination}")

    companions = same_stem_companions(source)
    if companions and not args.force_reconvert:
        names = ", ".join(str(path) for path in companions)
        fail(
            "existing Markdown companion found next to source; use it instead "
            f"of reconverting: {names}"
        )
    if source.suffix.lower() == ".pdf" and not args.confirmed_no_companion and not args.force_reconvert:
        fail(
            "refusing PDF conversion until Zotero children were checked; use an "
            "existing .md/.mmd companion or pass --confirmed-no-companion after "
            "verifying that none exists"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    require_snip_auth()
    convert(source, destination)
    if not destination.exists():
        fail(f"Mathpix reported success but no output file was created: {destination}")
    print(f"input={source}")
    print(f"output={destination}")
    print("auth=snip-token")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
