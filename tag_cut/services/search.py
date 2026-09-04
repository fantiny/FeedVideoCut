"""Tag-based search across analyzed batches (materials + shots)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Fallback when taxonomy.search.skip_match_types is empty
_DEFAULT_SKIP_MATCH_TYPES = frozenset({
    "object_detection",
    "lighting_metrics",
    "edit_value",
    "commercial_evidence",
    "usable_duration",
    "platform_fit",
    "compliance",
    "relation_chain",
    "subject_layout",
})


def _skip_match_types() -> frozenset[str]:
    try:
        from services.taxonomy import load_taxonomy
        configured = load_taxonomy().skip_match_types()
        if configured:
            return frozenset(configured)
    except Exception:  # noqa: BLE001
        pass
    return _DEFAULT_SKIP_MATCH_TYPES


def _value_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, (str, int, float, bool)):
                parts.append(str(item))
            elif isinstance(item, dict) and "class_name" in item:
                parts.append(str(item.get("class_name") or ""))
        return " ".join(parts)
    if isinstance(value, dict):
        # Only shallow string fields — avoid full JSON dumps
        parts = []
        for k, v in value.items():
            if isinstance(v, (str, int, float, bool)):
                parts.append(f"{k}:{v}")
        return " ".join(parts)
    return ""


def _compact_value(value: Any) -> Any:
    """Shrink heavy label values for search hit payloads."""
    if isinstance(value, dict):
        if "class_name" in value:
            return value.get("class_name")
        # keep short dicts; summarize long ones
        if len(json.dumps(value, ensure_ascii=False)) > 120:
            keys = list(value.keys())[:6]
            return {k: value[k] for k in keys if isinstance(value[k], (str, int, float, bool))}
    if isinstance(value, list) and len(value) > 8:
        return value[:8]
    return value


def _label_matches(label: dict, q: str, label_type: str | None, layer: str | None) -> bool:
    lt = str(label.get("label_type") or "")
    if layer and label.get("layer") != layer:
        return False
    if label_type and lt != label_type:
        return False
    if lt in _skip_match_types() and not label_type:
        return False
    if not q:
        return True
    blob = f"{lt} {_value_text(label.get('label_value'))}".lower()
    return q in blob


def _public_keyframe(path: str | None, data_root: Path) -> str | None:
    if not path:
        return None
    try:
        from services.paths import public_data_url
        return public_data_url(path, data_root) or path
    except Exception:  # noqa: BLE001
        return path


def search_labels(
    data_root: Path,
    query: str = "",
    *,
    batch_id: str | None = None,
    label_type: str | None = None,
    layer: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Search shot labels. Empty query with filters still returns matching rows.
    """
    q = (query or "").strip().lower()
    limit = max(1, min(int(limit), 500))
    hits: list[dict[str, Any]] = []
    if not data_root.exists():
        return {"query": query, "count": 0, "hits": []}

    batch_dirs = []
    if batch_id:
        d = data_root / batch_id
        if d.is_dir():
            batch_dirs = [d]
    else:
        batch_dirs = [p for p in sorted(data_root.iterdir()) if p.is_dir()]

    for batch_dir in batch_dirs:
        for mat_dir in sorted(batch_dir.iterdir()):
            if not mat_dir.is_dir():
                continue
            mf = mat_dir / "material.json"
            lf = mat_dir / "labels.json"
            sf = mat_dir / "shots.json"
            if not mf.exists() or not lf.exists() or not sf.exists():
                continue
            try:
                material = json.loads(mf.read_text())
                labels = json.loads(lf.read_text())
                shots = {s["id"]: s for s in json.loads(sf.read_text())}
            except (json.JSONDecodeError, KeyError, TypeError, OSError):
                continue

            by_shot: dict[str, list[dict]] = {}
            for lb in labels:
                if not _label_matches(lb, q, label_type, layer):
                    continue
                sid = lb.get("shot_id")
                if not sid:
                    continue
                by_shot.setdefault(sid, []).append({
                    "layer": lb.get("layer"),
                    "label_type": lb.get("label_type"),
                    "label_value": _compact_value(lb.get("label_value")),
                    "confidence": lb.get("confidence"),
                    "source": lb.get("source"),
                })

            for sid, matched in by_shot.items():
                shot = shots.get(sid)
                if not shot:
                    continue
                kf = (shot.get("key_frames") or {}).get("mid")
                hits.append({
                    "batch_id": batch_dir.name,
                    "material_id": material.get("id") or mat_dir.name,
                    "material_name": material.get("file_name") or "",
                    "file_path": material.get("file_path") or "",
                    "shot_id": sid,
                    "start_time": shot.get("start_time"),
                    "end_time": shot.get("end_time"),
                    "is_rejected": bool(shot.get("is_rejected")),
                    "quality_grade": shot.get("quality_grade"),
                    "keyframe_mid": _public_keyframe(kf, data_root),
                    "matched_labels": matched[:12],
                    "match_count": len(matched),
                })
                if len(hits) >= limit:
                    return {"query": query, "count": len(hits), "hits": hits, "truncated": True}

    return {"query": query, "count": len(hits), "hits": hits, "truncated": False}


def list_label_facets(
    data_root: Path,
    *,
    batch_id: str | None = None,
    max_values: int = 40,
) -> dict[str, Any]:
    """Collect frequent label_type / sample values for search UI hints."""
    type_counts: dict[str, int] = {}
    value_samples: dict[str, set[str]] = {}

    batch_dirs = []
    if batch_id:
        d = data_root / batch_id
        if d.is_dir():
            batch_dirs = [d]
    else:
        batch_dirs = [p for p in sorted(data_root.iterdir()) if p.is_dir()] if data_root.exists() else []

    for batch_dir in batch_dirs:
        for mat_dir in batch_dir.iterdir():
            lf = mat_dir / "labels.json"
            if not lf.exists():
                continue
            try:
                labels = json.loads(lf.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            for lb in labels:
                lt = str(lb.get("label_type") or "")
                if not lt or lt in _skip_match_types():
                    continue
                type_counts[lt] = type_counts.get(lt, 0) + 1
                text = _value_text(lb.get("label_value"))
                if text:
                    for token in text.replace("/", " ").split():
                        if token and len(token) <= 32:
                            value_samples.setdefault(lt, set()).add(token)

    types = sorted(type_counts.items(), key=lambda x: (-x[1], x[0]))
    return {
        "label_types": [{"type": t, "count": c} for t, c in types[:80]],
        "sample_values": {
            t: sorted(list(vals))[:max_values]
            for t, vals in list(value_samples.items())[:40]
        },
    }
