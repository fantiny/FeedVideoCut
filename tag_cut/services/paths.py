"""Path utilities for tag_cut data layout."""
from pathlib import Path
import hashlib


def material_id(video_path: Path) -> str:
    """Stable ID: sha1 of the absolute path string (first 12 hex chars)."""
    return hashlib.sha1(str(video_path.resolve()).encode()).hexdigest()[:12]


def material_dir_path(data_root: Path, batch_id: str, mat_id: str) -> Path:
    """Return the material directory path (does NOT create it)."""
    return data_root / batch_id / mat_id


def ensure_material_dir(data_root: Path, batch_id: str, mat_id: str) -> Path:
    """Return the material directory path, creating it if needed."""
    d = material_dir_path(data_root, batch_id, mat_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


# backward-compat alias
material_dir = ensure_material_dir
