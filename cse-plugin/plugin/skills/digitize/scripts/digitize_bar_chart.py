#!/usr/bin/env python
"""Digitize calibrated bar-chart values from an image."""

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


class ValueAxisTransform:
    def __init__(self, axis: dict[str, Any]) -> None:
        self.v1p = _point(axis["v1_pixel"], "value_axis.v1_pixel")
        self.v2p = _point(axis["v2_pixel"], "value_axis.v2_pixel")
        self.v1 = float(axis["v1_value"])
        self.v2 = float(axis["v2_value"])
        self.scale = str(axis.get("scale", "linear"))
        self.vector = self.v2p - self.v1p
        if float(np.dot(self.vector, self.vector)) == 0:
            raise ValueError("value_axis calibration points must not be identical")

    def pixel_to_value(self, px: float, py: float) -> float:
        p = np.array([float(px), float(py)], dtype=np.float64)
        t = float(np.dot(p - self.v1p, self.vector) / np.dot(self.vector, self.vector))
        return _scale_value(t, self.v1, self.v2, self.scale)


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


def _category_for(center: float, categories: list[dict[str, Any]]) -> str:
    for category in categories:
        span = category.get("span")
        if isinstance(span, list) and len(span) == 2 and float(span[0]) <= center <= float(span[1]):
            return str(category.get("name", ""))
    return ""


def _extract_components(mask: np.ndarray, min_area: float) -> list[tuple[int, int, int, int, float]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[tuple[int, int, int, int, float]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        boxes.append((x, y, x + w, y + h, area))
    return sorted(boxes, key=lambda b: (b[0], b[1]))


def digitize(image_path: Path, config_path: Path) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    bar_config = config["bar"]
    orientation = str(bar_config.get("orientation", "vertical"))
    if orientation not in {"vertical", "horizontal"}:
        raise ValueError("bar.orientation must be 'vertical' or 'horizontal'")
    transform = ValueAxisTransform(bar_config["value_axis"])
    baseline_value = float(bar_config.get("baseline_value", 0.0))
    categories = config.get("categories", [])
    roi = _roi_mask(image.shape[:2], config.get("roi"))

    rows: list[dict[str, Any]] = []
    for series in config.get("series", []):
        name = str(series.get("name", "series"))
        mask = _series_mask(image, series, roi)
        boxes = _extract_components(mask, float(series.get("min_area", 10)))
        for left, top, right, bottom, _area in boxes:
            center_x = (left + right) / 2.0
            center_y = (top + bottom) / 2.0
            if orientation == "vertical":
                endpoint_candidates = [(center_x, top), (center_x, bottom)]
                category = _category_for(center_x, categories)
            else:
                endpoint_candidates = [(left, center_y), (right, center_y)]
                category = _category_for(center_y, categories)

            endpoint = max(
                endpoint_candidates,
                key=lambda p: abs(transform.pixel_to_value(p[0], p[1]) - baseline_value),
            )
            value = transform.pixel_to_value(endpoint[0], endpoint[1])
            rows.append(
                {
                    "series": name,
                    "category": category,
                    "value": value,
                    "baseline_value": baseline_value,
                    "pixel_center_x": center_x,
                    "pixel_center_y": center_y,
                    "pixel_endpoint_x": endpoint[0],
                    "pixel_endpoint_y": endpoint[1],
                    "pixel_left": left,
                    "pixel_top": top,
                    "pixel_right": right,
                    "pixel_bottom": bottom,
                }
            )
    return image, rows, config


def _draw_overlay(image: np.ndarray, rows: list[dict[str, Any]], out: Path) -> None:
    overlay = image.copy()
    for row in rows:
        left = int(row["pixel_left"])
        top = int(row["pixel_top"])
        right = int(row["pixel_right"])
        bottom = int(row["pixel_bottom"])
        endpoint = (int(round(row["pixel_endpoint_x"])), int(round(row["pixel_endpoint_y"])))
        cv2.rectangle(overlay, (left, top), (right, bottom), (0, 255, 255), 2, lineType=cv2.LINE_AA)
        cv2.circle(overlay, endpoint, 4, (0, 0, 255), -1, lineType=cv2.LINE_AA)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), overlay)


def main() -> int:
    parser = argparse.ArgumentParser(description="Digitize calibrated bar-chart data from an image.")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--metadata-out", type=Path)
    args = parser.parse_args()

    image, rows, config = digitize(args.image, args.config)
    fieldnames = [
        "series",
        "category",
        "value",
        "baseline_value",
        "pixel_center_x",
        "pixel_center_y",
        "pixel_endpoint_x",
        "pixel_endpoint_y",
        "pixel_left",
        "pixel_top",
        "pixel_right",
        "pixel_bottom",
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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
