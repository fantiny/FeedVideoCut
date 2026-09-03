"""Shot scale (景别) estimation from largest detected subject bbox."""

def estimate_shot_scale(detections: list[dict]) -> tuple[str, float]:
    """Return (scale_label, confidence). Uses largest subject normalised height."""
    if not detections:
        return "未知", 0.0
    best = max(detections, key=lambda d: d["bbox_norm"][3] - d["bbox_norm"][1])
    norm_h = best["bbox_norm"][3] - best["bbox_norm"][1]
    if norm_h > 0.60:
        scale = "大特写"
    elif norm_h > 0.40:
        scale = "特写"
    elif norm_h > 0.25:
        scale = "近景"
    elif norm_h > 0.10:
        scale = "中景"
    else:
        scale = "全景"
    return scale, round(best["confidence"], 4)
