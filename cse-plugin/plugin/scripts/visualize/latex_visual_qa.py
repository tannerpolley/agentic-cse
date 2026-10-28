#!/usr/bin/env python3
"""Rasterize a PDF and report conservative text-layout risks."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


PROFILES = {
    "article": {"edge_margin": 12.0, "minimum_gap": 1.5, "graphic_gap": 0.75},
    "beamer": {"edge_margin": 1.0, "minimum_gap": 2.0, "graphic_gap": 0.75},
    "standalone": {"edge_margin": 3.0, "minimum_gap": 1.0, "graphic_gap": 0.75},
}


def command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, text=True, capture_output=True, check=False)


def clean_xml(text: str) -> str:
    text = "".join(
        character for character in text if character in "\t\n\r" or ord(character) >= 32
    )

    def valid_reference(match: re.Match[str]) -> str:
        value = int(match.group(1), 16)
        return match.group(0) if value in (9, 10, 13) or value >= 32 else ""

    return re.sub(r"&#x([0-9A-Fa-f]+);", valid_reference, text)


def require_tools(contact_sheet: bool) -> dict[str, str]:
    names = ["pdffonts", "pdftotext", "pdftoppm", "mutool"]
    if contact_sheet:
        names.append("montage")
    resolved = {name: shutil.which(name) or "" for name in names}
    missing = [name for name, path in resolved.items() if not path]
    if missing:
        raise RuntimeError(f"required executable unavailable: {', '.join(missing)}")
    return resolved


def parse_text_boxes(pdf: Path, pdftotext: str) -> list[dict]:
    result = command(pdftotext, "-bbox-layout", str(pdf), "-")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "pdftotext failed")
    root = ET.fromstring(clean_xml(result.stdout))
    pages = []
    for page_number, page in enumerate(
        (element for element in root.iter() if element.tag.endswith("page")), start=1
    ):
        lines = []
        for line in (element for element in page.iter() if element.tag.endswith("line")):
            words = [
                "".join(word.itertext()).strip()
                for word in line
                if word.tag.endswith("word")
            ]
            if words:
                lines.append(
                    {
                        "text": " ".join(word for word in words if word),
                        "x0": float(line.attrib["xMin"]),
                        "y0": float(line.attrib["yMin"]),
                        "x1": float(line.attrib["xMax"]),
                        "y1": float(line.attrib["yMax"]),
                    }
                )
        pages.append(
            {
                "page": page_number,
                "width": float(page.attrib["width"]),
                "height": float(page.attrib["height"]),
                "lines": lines,
            }
        )
    return pages


def transformed(point: tuple[float, float], matrix: tuple[float, ...]) -> tuple[float, float]:
    x, y = point
    a, b, c, d, e, f = matrix
    return a * x + c * y + e, b * x + d * y + f


def segment_box(points: list[tuple[float, float]], padding: float) -> dict:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "x0": min(xs) - padding,
        "y0": min(ys) - padding,
        "x1": max(xs) + padding,
        "y1": max(ys) + padding,
    }


def bezier_points(points: list[tuple[float, float]], steps: int = 32) -> list[tuple[float, float]]:
    sampled = []
    degree = len(points) - 1
    for index in range(steps + 1):
        t = index / steps
        if degree == 2:
            weights = ((1 - t) ** 2, 2 * (1 - t) * t, t**2)
        else:
            weights = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t**2, t**3)
        sampled.append(
            (
                sum(weight * point[0] for weight, point in zip(weights, points)),
                sum(weight * point[1] for weight, point in zip(weights, points)),
            )
        )
    return sampled


def parse_stroke_boxes(pdf: Path, mutool: str) -> list[list[dict]]:
    result = command(mutool, "draw", "-F", "trace", "-o", "-", str(pdf))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "mutool trace failed")
    root = ET.fromstring(clean_xml(result.stdout))
    pages = []
    for page in (element for element in root.iter() if element.tag.endswith("page")):
        segments = []
        for path in (
            element for element in page.iter() if element.tag.endswith("stroke_path")
        ):
            matrix = tuple(float(value) for value in path.attrib["transform"].split())
            scale = max(math.hypot(matrix[0], matrix[1]), math.hypot(matrix[2], matrix[3]))
            padding = float(path.attrib.get("linewidth", "0")) * scale / 2
            current = None
            start = None
            for operation in path:
                tag = operation.tag.rsplit("}", 1)[-1]
                if tag == "moveto":
                    current = transformed(
                        (float(operation.attrib["x"]), float(operation.attrib["y"])),
                        matrix,
                    )
                    start = current
                elif tag == "lineto" and current is not None:
                    endpoint = transformed(
                        (float(operation.attrib["x"]), float(operation.attrib["y"])),
                        matrix,
                    )
                    segments.append(segment_box([current, endpoint], padding))
                    current = endpoint
                elif tag == "curveto" and current is not None:
                    points = [current]
                    for suffix in ("1", "2", "3"):
                        points.append(
                            transformed(
                                (
                                    float(operation.attrib[f"x{suffix}"]),
                                    float(operation.attrib[f"y{suffix}"]),
                                ),
                                matrix,
                            )
                        )
                    segments.append(segment_box(bezier_points(points), padding))
                    current = points[-1]
                elif tag == "quadto" and current is not None:
                    points = [current]
                    for suffix in ("1", "2"):
                        points.append(
                            transformed(
                                (
                                    float(operation.attrib[f"x{suffix}"]),
                                    float(operation.attrib[f"y{suffix}"]),
                                ),
                                matrix,
                            )
                        )
                    segments.append(segment_box(bezier_points(points), padding))
                    current = points[-1]
                elif tag == "closepath" and current is not None and start is not None:
                    segments.append(segment_box([current, start], padding))
                    current = start
        pages.append(segments)
    return pages


def intersection(first: dict, second: dict) -> tuple[float, float]:
    return (
        max(0.0, min(first["x1"], second["x1"]) - max(first["x0"], second["x0"])),
        max(0.0, min(first["y1"], second["y1"]) - max(first["y0"], second["y0"])),
    )


def substantial(text: str) -> bool:
    return sum(character.isalnum() for character in text) >= 4


def box_distance(first: dict, second: dict) -> float:
    x_gap = max(first["x0"] - second["x1"], second["x0"] - first["x1"], 0.0)
    y_gap = max(first["y0"] - second["y1"], second["y0"] - first["y1"], 0.0)
    return math.hypot(x_gap, y_gap)


def approximate_ink_box(line: dict) -> dict:
    width = line["x1"] - line["x0"]
    height = line["y1"] - line["y0"]
    horizontal_inset = min(0.75, 0.02 * width)
    vertical_inset = 0.20 * height
    return {
        **line,
        "x0": line["x0"] + horizontal_inset,
        "y0": line["y0"] + vertical_inset,
        "x1": line["x1"] - horizontal_inset,
        "y1": line["y1"] - vertical_inset,
    }


def inspect_graphic_clearance(page: dict, strokes: list[dict], minimum_gap: float) -> list[dict]:
    issues = []
    for line in page["lines"]:
        if not substantial(line["text"]):
            continue
        ink = approximate_ink_box(line)
        line_width = ink["x1"] - ink["x0"]
        line_height = ink["y1"] - ink["y0"]
        candidates = []
        for stroke in strokes:
            overlap_x, overlap_y = intersection(ink, stroke)
            aligned = (
                overlap_x >= 0.15 * line_width
                or overlap_y >= 0.15 * line_height
            )
            distance = box_distance(ink, stroke)
            if aligned and distance < minimum_gap:
                candidates.append((distance, stroke))
        if not candidates:
            continue
        distance, stroke = min(candidates, key=lambda candidate: candidate[0])
        overlap_x, overlap_y = intersection(ink, stroke)
        overlap = overlap_x > 0 and overlap_y > 0
        issues.append(
            {
                "severity": "warning",
                "code": "text_graphic_overlap" if overlap else "tight_text_graphic_clearance",
                "page": page["page"],
                "text": line["text"],
                "gap_points": round(distance, 2),
            }
        )
    return issues


def inspect_page(page: dict, profile: dict) -> list[dict]:
    issues = []
    margin = profile["edge_margin"]
    for line in page["lines"]:
        if (
            line["x0"] < margin
            or line["y0"] < margin
            or page["width"] - line["x1"] < margin
            or page["height"] - line["y1"] < margin
        ):
            issues.append(
                {
                    "severity": "warning",
                    "code": "text_near_page_edge",
                    "page": page["page"],
                    "text": line["text"],
                }
            )

    # ponytail: quadratic per-page scan; add a spatial index only if dense PDFs make it slow.
    for index, first in enumerate(page["lines"]):
        for second in page["lines"][index + 1 :]:
            if not substantial(first["text"]) or not substantial(second["text"]):
                continue
            overlap_x, overlap_y = intersection(first, second)
            first_width = first["x1"] - first["x0"]
            second_width = second["x1"] - second["x0"]
            first_height = first["y1"] - first["y0"]
            second_height = second["y1"] - second["y0"]
            if (
                overlap_x >= 0.25 * min(first_width, second_width)
                and overlap_y >= 0.65 * min(first_height, second_height)
            ):
                issues.append(
                    {
                        "severity": "error",
                        "code": "text_overlap",
                        "page": page["page"],
                        "text": [first["text"], second["text"]],
                    }
                )
                continue

            horizontal_overlap = overlap_x >= 0.25 * min(first_width, second_width)
            vertical_gap = max(first["y0"], second["y0"]) - min(
                first["y1"], second["y1"]
            )
            if horizontal_overlap and 0 <= vertical_gap < profile["minimum_gap"]:
                issues.append(
                    {
                        "severity": "warning",
                        "code": "tight_text_clearance",
                        "page": page["page"],
                        "text": [first["text"], second["text"]],
                        "gap_points": round(vertical_gap, 2),
                    }
                )
    return issues


def clear_generated_files(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for pattern in ("page-*.png", "contact-sheet.png"):
        for path in directory.glob(pattern):
            if path.is_file():
                path.unlink()


def render_pages(pdf: Path, root: Path, pdftoppm: str, dpi: int) -> dict[str, list[Path]]:
    rendered = {}
    for name, extra in (("color", []), ("grayscale", ["-gray"])):
        directory = root / name
        clear_generated_files(directory)
        result = command(
            pdftoppm,
            "-png",
            *extra,
            "-r",
            str(dpi),
            str(pdf),
            str(directory / "page"),
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or f"failed to render {name} pages")
        rendered[name] = sorted(
            directory.glob("page-*.png"),
            key=lambda path: int(path.stem.rsplit("-", 1)[1]),
        )
    return rendered


def make_contact_sheet(pages: list[Path], output: Path, montage: str) -> None:
    if not pages:
        return
    result = command(
        montage,
        *(str(page) for page in pages),
        "-thumbnail",
        "320x",
        "-tile",
        "4x",
        "-geometry",
        "+8+8",
        str(output),
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "contact-sheet generation failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--contact-sheet", action="store_true")
    parser.add_argument("--warnings-as-errors", action="store_true")
    arguments = parser.parse_args()

    if not arguments.pdf.is_file() or not arguments.pdf.stat().st_size:
        parser.error(f"PDF is missing or empty: {arguments.pdf}")
    if arguments.dpi < 72:
        parser.error("DPI must be at least 72")

    try:
        tools = require_tools(arguments.contact_sheet)
        fonts = command(tools["pdffonts"], str(arguments.pdf))
        if fonts.returncode:
            raise RuntimeError(fonts.stderr.strip() or "pdffonts failed")
        if "Type 3" in fonts.stdout:
            raise RuntimeError("Type 3 fonts found; attribute each source and replace bitmap fonts. For T1 venue classes use Latin Modern sans/typewriter; for Matplotlib use pdf.fonttype: 42.\n" + fonts.stdout)
        pages = parse_text_boxes(arguments.pdf, tools["pdftotext"])
        if not pages:
            raise RuntimeError("PDF contains no pages")
        stroke_pages = parse_stroke_boxes(arguments.pdf, tools["mutool"])
        if len(stroke_pages) != len(pages):
            raise RuntimeError("text and vector page counts differ")
        issues = [
            issue
            for page, strokes in zip(pages, stroke_pages)
            for issue in (
                inspect_page(page, PROFILES[arguments.profile])
                + inspect_graphic_clearance(
                    page,
                    strokes,
                    PROFILES[arguments.profile]["graphic_gap"],
                )
            )
        ]
        rendered = render_pages(
            arguments.pdf,
            arguments.output_dir / "pages",
            tools["pdftoppm"],
            arguments.dpi,
        )
        if arguments.contact_sheet:
            make_contact_sheet(
                rendered["color"],
                arguments.output_dir / "contact-sheet.png",
                tools["montage"],
            )
    except (ET.ParseError, OSError, RuntimeError) as error:
        print(f"visual QA failed: {error}", file=sys.stderr)
        return 2

    has_error = any(issue["severity"] == "error" for issue in issues)
    has_warning = any(issue["severity"] == "warning" for issue in issues)
    status = "fail" if has_error or (arguments.warnings_as_errors and has_warning) else "review"
    report = {
        "pdf": str(arguments.pdf.resolve()),
        "profile": arguments.profile,
        "dpi": arguments.dpi,
        "page_count": len(pages),
        "status": status,
        "issues": issues,
        "manual_review_required": True,
    }
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    (arguments.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{status}: {len(pages)} pages, {len(issues)} automated finding(s)")
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
