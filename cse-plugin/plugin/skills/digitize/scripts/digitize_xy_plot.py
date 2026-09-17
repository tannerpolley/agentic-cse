#!/usr/bin/env python
"""Digitize calibrated 2D XY plot data from an image.

This helper intentionally stays narrow: it extracts colored/thresholded points
or curves from a cropped 2D XY plot, maps pixels to calibrated axis values, and
writes a CSV plus an optional QA overlay.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _point(value: Any, name: str) -> np.ndarray:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be [x, y]")
    return np.array([float(value[0]), float(value[1])], dtype=np.float64)


def _scale_value(t: float, v1: float, v2: float, scale: str) -> float:
    if scale == "linear":
        return v1 + t * (v2 - v1)
    if scale == "log10":
        if v1 <= 0 or v2 <= 0:
            raise ValueError("log10 calibration values must be positive")
        return 10 ** (math.log10(v1) + t * (math.log10(v2) - math.log10(v1)))
    raise ValueError(f"Unsupported scale: {scale!r}")


class AxisTransform:
    def __init__(self, axis: dict[str, Any]) -> None:
        self.x1p = _point(axis["x1_pixel"], "axis.x1_pixel")
        self.x2p = _point(axis["x2_pixel"], "axis.x2_pixel")
        self.y1p = _point(axis["y1_pixel"], "axis.y1_pixel")
        self.y2p = _point(axis["y2_pixel"], "axis.y2_pixel")
        self.x1v = float(axis["x1_value"])
        self.x2v = float(axis["x2_value"])
        self.y1v = float(axis["y1_value"])
        self.y2v = float(axis["y2_value"])
        self.x_scale = axis.get("x_scale", "linear")
        self.y_scale = axis.get("y_scale", "linear")

        self.xv = self.x2p - self.x1p
        self.yv = self.y2p - self.y1p
        if float(np.dot(self.xv, self.xv)) == 0 or float(np.dot(self.yv, self.yv)) == 0:
            raise ValueError("Axis calibration points must not be identical")

    def pixel_to_data(self, px: float, py: float) -> tuple[float, float]:
        p = np.array([px, py], dtype=np.float64)
        tx = float(np.dot(p - self.x1p, self.xv) / np.dot(self.xv, self.xv))
        ty = float(np.dot(p - self.y1p, self.yv) / np.dot(self.yv, self.yv))
        return (
            _scale_value(tx, self.x1v, self.x2v, self.x_scale),
            _scale_value(ty, self.y1v, self.y2v, self.y_scale),
        )


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


def _series_mask(image_bgr: np.ndarray, config: dict[str, Any], roi_mask: np.ndarray) -> np.ndarray:
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

    mask = cv2.bitwise_and(mask, roi_mask)
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


def _extract_curve(mask: np.ndarray, min_pixels_per_column: int) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    ys_by_x = np.where(mask > 0)
    if len(ys_by_x[0]) == 0:
        return points
    ys, xs = ys_by_x
    for x in np.unique(xs):
        y_values = ys[xs == x]
        if len(y_values) < min_pixels_per_column:
            continue
        points.append((float(x), float(np.median(y_values))))
    return points


def _draw_overlay(image: np.ndarray, rows: list[dict[str, Any]], out: Path) -> None:
    overlay = image.copy()
    for row in rows:
        px = int(round(float(row["pixel_x"])))
        py = int(round(float(row["pixel_y"])))
        cv2.circle(overlay, (px, py), 3, (0, 255, 255), 1, lineType=cv2.LINE_AA)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), overlay)


def digitize(image_path: Path, config_path: Path) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    transform = AxisTransform(config["axis"])
    roi = _roi_mask(image.shape[:2], config.get("roi"))

    rows: list[dict[str, Any]] = []
    for series in config.get("series", []):
        name = str(series.get("name", "series"))
        mode = str(series.get("mode", "points"))
        mask = _series_mask(image, series, roi)
        if mode == "points":
            pixels = _extract_points(mask, float(series.get("min_area", 3)))
        elif mode == "curve":
            pixels = _extract_curve(mask, int(series.get("min_pixels_per_column", 1)))
        else:
            raise ValueError(f"Unsupported series mode: {mode!r}")

        stride = max(1, int(series.get("stride", 1)))
        for px, py in pixels[::stride]:
            x, y = transform.pixel_to_data(px, py)
            rows.append(
                {
                    "series": name,
                    "x": x,
                    "y": y,
                    "pixel_x": px,
                    "pixel_y": py,
                }
            )
    return image, rows, config


def main() -> int:
    parser = argparse.ArgumentParser(description="Digitize calibrated XY plot data from an image.")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--metadata-out", type=Path)
    args = parser.parse_args()

    image, rows, config = digitize(args.image, args.config)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["series", "x", "y", "pixel_x", "pixel_y"])
        writer.writeheader()
        writer.writerows(rows)

    if args.overlay:
        _draw_overlay(image, rows, args.overlay)

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
