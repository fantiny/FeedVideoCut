"""Burned-in subtitle detection from a frame (heuristic, no model).

The bottom caption band of subtitled ads has a much higher edge density than
the frame center. We compare bands to decide presence, and locate the band
(bottom vs middle) by which comparison is stronger.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter

_THRESHOLD = 1.35  # bottom/center edge-density ratio that implies subtitles


def _edge_ratio(img: Image.Image, y0: float, y1: float) -> float:
    w, h = img.size
    band = img.crop((0, int(h * y0), w, int(h * y1)))
    px = list(band.getdata())
    return sum(1 for v in px if v > 60) / max(1, len(px))


def detect_subtitle(img_path: Path | str) -> tuple[bool, str, float]:
    """
    Returns (has_subtitle, position, score).
    position: "底部" | "中部" | "无". score = bottom/center edge density ratio.
    """
    p = Path(img_path)
    if not p.is_file():
        return False, "无", 0.0
    try:
        img = Image.open(p).convert("L")
    except OSError:
        return False, "无", 0.0
    edges = img.filter(ImageFilter.FIND_EDGES)

    def ratio(y0: float, y1: float) -> float:
        return _edge_ratio(edges, y0, y1)

    bottom = ratio(0.68, 0.98) / max(ratio(0.30, 0.55), 1e-4)
    middle = ratio(0.50, 0.80) / max(ratio(0.20, 0.45), 1e-4)

    if bottom >= _THRESHOLD and bottom >= middle:
        return True, "底部", round(min(1.0, (bottom - 1.0) / 2.0), 2)
    if middle >= _THRESHOLD:
        return True, "中部", round(min(1.0, (middle - 1.0) / 2.0), 2)
    return False, "无", round(max(0.0, min(1.0, 1.0 - bottom)), 2)
