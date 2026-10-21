#!/usr/bin/env python
"""Digitize calibrated ternary plot data from an image.

The script maps extracted pixels to ternary composition values using a
three-vertex barycentric calibration. It is intentionally conservative:
calibration and QA overlay review are still required before trusting output.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _point(value: Any, name: str) -> np.ndarray:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be [x, y]")
    return np.array([float(value[0]), float(value[1])], dtype=np.float64)


class TernaryTransform:
    def __init__(self, config: dict[str, Any]) -> None:
        self.a_name = str(config.get("a_name", "A"))
        self.b_name = str(config.get("b_name", "B"))
        self.c_name = str(config.get("c_name", "C"))
        self.total = float(config.get("total", 100.0))
        self.a = _point(config["a_pixel"], "ternary.a_pixel")
        self.b = _point(config["b_pixel"], "ternary.b_pixel")
        self.c = _point(config["c_pixel"], "ternary.c_pixel")

        matrix = np.array(
            [
                [self.a[0], self.b[0], self.c[0]],
                [self.a[1], self.b[1], self.c[1]],
                [1.0, 1.0, 1.0],
            ],
            dtype=np.float64,
        )
        det = float(np.linalg.det(matrix))
        if abs(det) < 1e-9:
            raise ValueError("Ternary calibration vertices must form a non-degenerate triangle")
        self._inverse = np.linalg.inv(matrix)

    def pixel_to_components(self, px: float, py: float) -> tuple[float, float, float]:
        weights = self._inverse @ np.array([float(px), float(py), 1.0], dtype=np.float64)
        return tuple(float(v * self.total) for v in weights)

    def inside(self, px: float, py: float, tolerance: float = 0.02) -> bool:
        comps = np.array(self.pixel_to_components(px, py), dtype=np.float64) / self.total
        return bool(np.all(comps >= -tolerance) and np.all(comps <= 1.0 + tolerance))

    def triangle_mask(self, shape: tuple[int, int]) -> np.ndarray:
        mask = np.zeros(shape, dtype=np.uint8)
        points = np.array([[self.a, self.b, self.c]], dtype=np.int32)
        cv2.fillPoly(mask, points, 255)
        return mask


def _roi_mask(shape: tuple[int, int], roi: list[int] | None) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    if roi is None:
        mask[:, :] = 255
        return mask
    if len(roi) != 4:
        raise ValueError("roi must be [left, top, right, bottom]")
    left, top, right, bottom = [int(v) for v in roi]
    h, w = shape
    left = max(0, min(w, left))
    right = max(0, min(w, right))
    top = max(0, min(h, top))
    bottom = max(0, min(h, bottom))
    if right <= left or bottom <= top:
        raise ValueError("roi has no positive area")
    mask[top:bottom, left:right] = 255
    return mask


def _series_mask(image_bgr: np.ndarray, config: dict[str, Any], allowed_mask: np.ndarray) -> np.ndarray:
    if "hsv_lower" in config and "hsv_upper" in config:
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        lower = np.array(config["hsv_lower"], dtype=np.uint8)
        upper = np.array(config["hsv_upper"], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
    elif "bgr_lower" in config and "bgr_upper" in config:
        lower = np.array(config["bgr_lower"], dtype=np.uint8)
        upper = np.array(config["bgr_upper"], dtype=np.uint8)
        mask = cv2.inRange(image_bgr, lower, upper)
    else:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        threshold = int(config.get("gray_threshold", 160))
        mode = cv2.THRESH_BINARY_INV if config.get("dark_on_light", True) else cv2.THRESH_BINARY
        _, mask = cv2.threshold(gray, threshold, 255, mode)

    mask = cv2.bitwise_and(mask, allowed_mask)
    kernel_size = int(config.get("morph_kernel", 1))
    if kernel_size > 1:
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return mask


def _extract_points(mask: np.ndarray, min_area: float) -> list[tuple[float, float]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    points: list[tuple[float, float]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        points.append((moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]))
    return sorted(points, key=lambda p: (p[0], p[1]))


def _extract_pixels(mask: np.ndarray, stride: int) -> list[tuple[float, float]]:
    ys, xs = np.where(mask > 0)
    pixels = list(zip(xs.astype(float), ys.astype(float)))
    pixels.sort(key=lambda p: (p[0], p[1]))
    return pixels[:: max(1, stride)]


def _draw_overlay(image: np.ndarray, rows: list[dict[str, Any]], transform: TernaryTransform, out: Path) -> None:
    overlay = image.copy()
    triangle = np.array([[transform.a, transform.b, transform.c]], dtype=np.int32)
    cv2.polylines(overlay, triangle, isClosed=True, color=(255, 0, 0), thickness=2, lineType=cv2.LINE_AA)
    for row in rows:
        px = int(round(float(row["pixel_x"])))
        py = int(round(float(row["pixel_y"])))
        cv2.circle(overlay, (px, py), 3, (0, 255, 255), 1, lineType=cv2.LINE_AA)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), overlay)


def digitize(image_path: Path, config_path: Path) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any], TernaryTransform]:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    transform = TernaryTransform(config["ternary"])
    allowed = cv2.bitwise_and(transform.triangle_mask(image.shape[:2]), _roi_mask(image.shape[:2], config.get("roi")))
    tolerance = float(config.get("triangle_tolerance", 0.02))

    rows: list[dict[str, Any]] = []
    for series in config.get("series", []):
        name = str(series.get("name", "series"))
        mode = str(series.get("mode", "points"))
        mask = _series_mask(image, series, allowed)
        if mode == "points":
            pixels = _extract_points(mask, float(series.get("min_area", 3)))
        elif mode == "pixels":
            pixels = _extract_pixels(mask, int(series.get("stride", 10)))
        else:
            raise ValueError(f"Unsupported series mode: {mode!r}")

        for px, py in pixels:
            if not transform.inside(px, py, tolerance=tolerance):
                continue
            a, b, c = transform.pixel_to_components(px, py)
            rows.append(
                {
                    "series": name,
                    transform.a_name: a,
                    transform.b_name: b,
                    transform.c_name: c,
                    "pixel_x": px,
                    "pixel_y": py,
                }
            )
    return image, rows, config, transform


def main() -> int:
    parser = argparse.ArgumentParser(description="Digitize calibrated ternary plot data from an image.")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--metadata-out", type=Path)
    args = parser.parse_args()

    image, rows, config, transform = digitize(args.image, args.config)
    fieldnames = ["series", transform.a_name, transform.b_name, transform.c_name, "pixel_x", "pixel_y"]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    if args.overlay:
        _draw_overlay(image, rows, transform, args.overlay)

    if args.metadata_out:
        metadata = {
            "source_image": str(args.image),
            "config": config,
            "row_count": len(rows),
            "csv": str(args.out),
            "overlay": str(args.overlay) if args.overlay else None,
        }
        args.metadata_out.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_out.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote {len(rows)} rows to {args.out}")
    if args.overlay:
        print(f"Wrote QA overlay to {args.overlay}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
