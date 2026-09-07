"""Path utilities for tag_cut data layout."""
from pathlib import Path
import hashlib


def resolve_stored_path(raw: str | None, anchor: Path) -> Path | None:
    """Resolve a path stored in data JSONs: absolute as-is, relative vs anchor."""
    if not raw:
        return None
    p = Path(str(raw)).expanduser()
    if not p.is_absolute():
        p = anchor / p
    return p


def material_id(video_path: Path, anchor: Path | None = None) -> str:
    """
    Stable ID: sha1 of the path string (first 12 hex chars).

    With `anchor` (the workspace root that holds all sibling projects), the ID
    is computed from the path relative to it — stable across machines and
    mount points. Without anchor, falls back to the absolute path.
    """
    try:
        p = video_path.resolve()
        key = p.relative_to(anchor.resolve()).as_posix() if anchor else str(p)
    except (ValueError, OSError):
        key = str(video_path.resolve())
    return hashlib.sha1(key.encode()).hexdigest()[:12]


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


def resolve_media_path(raw: object, anchor: Path) -> Path | None:
    """Resolve a stored media path: absolute used as-is, relative against anchor."""
    if raw is None or str(raw) == "":
        return None
    p = Path(str(raw)).expanduser()
    if not p.is_absolute():
        p = anchor / p
    return p


def store_path(p: Path, anchor: Path) -> str:
    """Stringify a path for storage: relative to anchor when it lives under it."""
    try:
        resolved = p.resolve()
        return resolved.relative_to(anchor.resolve()).as_posix()
    except (ValueError, OSError):
        return str(p)


def public_data_url(abs_path: str | None, data_root: Path) -> str | None:
    """Convert an on-disk path under data_root to /files/... URL."""
    if not abs_path:
        return None
    try:
        rel = Path(abs_path).resolve().relative_to(data_root.resolve())
    except (ValueError, OSError):
        return None
    return f"/files/{rel.as_posix()}"
