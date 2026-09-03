"""
Shot scale (景别) estimation from the largest detected subject's bounding box.

Scale categories (standard Chinese film/TV terms):
  大特写 (extreme close-up): subject > 60% of frame height
  特写 (close-up):           40–60%
  近景 (medium close-up):    25–40%
  中景 (medium):             10–25%
  全景 (wide/full):          < 10%

If no detections, falls back to "未知".
"""

SCALE_LABELS = ["大特写", "特写", "近景", "中景", "全景"]


def estimate_shot_scale(detections: list[dict]) -> tuple[str, float]:
    """
    Return (scale_label, confidence).
    confidence = detection confidence of the subject used for estimation.
    """
    if not detections:
        return "未知", 0.0

    # Pick detection with largest normalised height
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
