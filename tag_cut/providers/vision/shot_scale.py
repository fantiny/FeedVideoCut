"""
Shot scale (景别) estimation from the largest detected subject's bounding box.

Thresholds and labels come from config/taxonomy.yaml → enums.shot_scale.
"""
from __future__ import annotations

from services.taxonomy import load_taxonomy


def estimate_shot_scale(detections: list[dict]) -> tuple[str, float]:
    """
    Return (scale_label, confidence).
    confidence = detection confidence of the subject used for estimation.
    """
    tax = load_taxonomy()
    unknown = tax.unknown("shot_scale")
    if not detections:
        return unknown, 0.0

    best = max(detections, key=lambda d: d["bbox_norm"][3] - d["bbox_norm"][1])
    norm_h = best["bbox_norm"][3] - best["bbox_norm"][1]
    scale = tax.shot_scale_from_height(norm_h)
    return scale, round(best["confidence"], 4)
