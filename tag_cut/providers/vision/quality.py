"""Image quality grade via Laplacian variance (sharpness proxy)."""
from pathlib import Path

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

def estimate_quality_grade(image_path: Path) -> tuple[str, float]:
    """Return (grade, score). Grade in {'A','B','C','?'}."""
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
