"""
Image quality grade estimation using Laplacian variance (sharpness proxy).

Grades (对齐设计文档):
  A: sharp, well-exposed  (Laplacian variance >= 150)
  B: acceptable           (40–150)
  C: blurry or very dark  (< 40)

Returns ('?', 0.0) if opencv is unavailable or image cannot be read.
"""
from pathlib import Path

try:
    import cv2  # type: ignore[import]
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


def estimate_quality_grade(image_path: Path) -> tuple[str, float]:
    """
    Return (grade, score) where grade in {'A','B','C','?'} and score
    is the Laplacian variance (higher = sharper).
    """
    if not _CV2_AVAILABLE:
        return "?", 0.0

    img = cv2.imread(str(image_path))
    if img is None:
        return "?", 0.0

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    if score >= 150:
        grade = "A"
    elif score >= 40:
        grade = "B"
    else:
        grade = "C"

    return grade, round(score, 2)
