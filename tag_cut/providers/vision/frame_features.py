"""
Frame-level visual feature heuristics for L1 business tags.

No deep learning required. Uses OpenCV when available; otherwise returns
safe defaults with low confidence.
"""
from __future__ import annotations

from pathlib import Path

try:
    import cv2  # type: ignore[import]
    import numpy as np  # type: ignore[import]
    _CV2 = True
except ImportError:
    _CV2 = False


def _read_gray(path: Path):
    if not _CV2 or not path.exists():
        return None
    img = cv2.imread(str(path))
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), img


def estimate_lighting(image_path: Path) -> tuple[str, float, dict]:
    """
    Return (lighting_type, confidence, metrics).
    lighting_type: 自然光 / 棚拍 / 混合 / 夜景
    """
    packed = _read_gray(image_path)
    if packed is None:
        return "未知", 0.0, {}
    gray, bgr = packed
    mean = float(gray.mean())
    std = float(gray.std())
    # crude color temperature proxy: B vs R channel mean
    b, g, r = cv2.split(bgr)
    warm = float(r.mean()) - float(b.mean())

    if mean < 55:
        label = "夜景"
        conf = 0.7
    elif mean > 140 and std < 45:
        label = "棚拍"
        conf = 0.55
    elif warm > 12:
        label = "自然光"
        conf = 0.5
    else:
        label = "混合"
        conf = 0.45
    return label, conf, {"brightness": round(mean, 1), "contrast": round(std, 1), "warmth": round(warm, 1)}


def estimate_camera_move(
    start_path: Path | None,
    end_path: Path | None,
) -> tuple[str, float]:
    """
    Heuristic camera move from start/end keyframe difference.
    Values: 固定 / 推 / 拉 / 摇 / 手持 / 微距 / 未知
    """
    if not start_path or not end_path:
        return "未知", 0.0
    a = _read_gray(Path(start_path))
    b = _read_gray(Path(end_path))
    if a is None or b is None:
        return "未知", 0.0
    g1, _ = a
    g2, _ = b
    g1 = cv2.resize(g1, (160, 160))
    g2 = cv2.resize(g2, (160, 160))
    diff = float(np.mean(cv2.absdiff(g1, g2)))
    # edge density as micro/close texture proxy
    edges = float(cv2.Canny(g2, 80, 160).mean())

    if diff < 6:
        return "固定", 0.65
    if edges > 40 and diff < 18:
        return "微距", 0.45
    if diff < 18:
        return "推", 0.4  # mild change — often push/pull
    if diff < 35:
        return "摇", 0.4
    return "手持", 0.5


def subject_layout(detections: list[dict]) -> dict:
    """
    Subject composition metrics from normalised bboxes.
    """
    if not detections:
        return {
            "subject_count": 0,
            "subject_types": [],
            "largest_ratio": 0.0,
            "position": "未知",
            "safe_zone_ok": True,
            "edge_risk": False,
        }

    types = sorted({d.get("class_name", "unknown") for d in detections})
    best = max(detections, key=lambda d: max(0.0, d["bbox_norm"][2] - d["bbox_norm"][0]) * max(0.0, d["bbox_norm"][3] - d["bbox_norm"][1]))
    x1, y1, x2, y2 = best["bbox_norm"]
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    ratio = w * h

    if cy < 0.33:
        pos = "上"
    elif cy > 0.66:
        pos = "下"
    elif cx < 0.33:
        pos = "左"
    elif cx > 0.66:
        pos = "右"
    else:
        pos = "中"

    edge_risk = x1 < 0.05 or y1 < 0.05 or x2 > 0.95 or y2 > 0.95
    # vertical short-video safe zone: keep subject away from bottom subtitle band
    safe_zone_ok = y2 < 0.82 and not edge_risk

    return {
        "subject_count": len(detections),
        "subject_types": types,
        "largest_ratio": round(ratio, 4),
        "largest_height_ratio": round(h, 4),
        "position": pos,
        "safe_zone_ok": safe_zone_ok,
        "edge_risk": edge_risk,
        "center": [round(cx, 3), round(cy, 3)],
    }
