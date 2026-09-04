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


def resolve_batch_path(raw: str, *, cwd: Path | None = None, input_root: Path | None = None) -> Path | None:
    """Resolve a user-supplied batch directory. Returns None if not found."""
    cwd = cwd or Path.cwd()
    p = Path(raw).expanduser()
    candidates: list[Path] = []
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.append((cwd / p).resolve())
        if input_root is not None:
            ir = input_root if input_root.is_absolute() else (cwd / input_root)
            candidates.append((ir / p.name).resolve())
            candidates.append((ir / p).resolve())
        candidates.append((cwd.parent / "input" / p.name).resolve())

    seen: set[str] = set()
    for cand in candidates:
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        if cand.exists() and cand.is_dir():
            return cand
    return None


def public_data_url(abs_path: str | None, data_root: Path) -> str | None:
    """Convert an on-disk path under data_root to /files/... URL."""
    if not abs_path:
        return None
    try:
        rel = Path(abs_path).resolve().relative_to(data_root.resolve())
    except (ValueError, OSError):
        return None
    return f"/files/{rel.as_posix()}"
