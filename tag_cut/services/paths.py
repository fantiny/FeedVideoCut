"""Path utilities for tag_cut data layout."""
from pathlib import Path
import hashlib


def material_id(video_path: Path) -> str:
    """Stable ID: sha1 of the absolute path string (first 12 hex chars)."""
    return hashlib.sha1(str(video_path.resolve()).encode()).hexdigest()[:12]


def material_dir(data_root: Path, batch_id: str, mat_id: str) -> Path:
    """Returns data_root/batch_id/mat_id, creates it if needed."""
    d = data_root / batch_id / mat_id
    d.mkdir(parents=True, exist_ok=True)
    return d
