"""
Export pipeline: produce index.json and index.csv for a batch.

Columns align with 素材库索引表 (sheet 03):
  编号, 一级分类建议, 二级分类建议, 文件名, 景别, 运镜,
  时长(s), 画面主体描述, 犬种/主体, 是否含人, 是否含LOGO,
  适用类型, 已用次数, 存储路径, 备注,
  hook_score, evidence_score, emotion_score, quality_grade
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_label(labels: list[dict], layer: str, label_type: str):
    for lb in labels:
        if lb.get("layer") == layer and lb.get("label_type") == label_type:
            return lb.get("label_value")
    return None


def _objects_of(labels: list[dict]) -> list[str]:
    return [
        lb["label_value"]["class_name"]
        for lb in labels
        if lb.get("layer") == "l1"
        and lb.get("label_type") == "object_detection"
        and isinstance(lb.get("label_value"), dict)
    ]


def _build_row(material: dict, shot: dict, shot_labels: list[dict], shot_scores: dict | None) -> dict:
    obj_classes = _objects_of(shot_labels)
    has_dog = "dog" in obj_classes
    has_person = "person" in obj_classes

    applicable_types = _first_label(shot_labels, "l4", "applicable_types") or []
    if isinstance(applicable_types, list):
        applicable_types_str = "/".join(applicable_types)
    else:
        applicable_types_str = str(applicable_types)

    behaviors = [
        lb["label_value"]
        for lb in shot_labels
        if lb.get("layer") == "l2" and lb.get("label_type") == "behavior"
    ]

    return {
        "编号": shot["id"],
        "一级分类建议": "01_视频素材",
        "二级分类建议": "V03_狗狗进食" if has_dog else "V04_人物出镜" if has_person else "V01_产品特写",
        "文件名": material.get("file_name", ""),
        "景别": _first_label(shot_labels, "l1", "shot_scale") or "未知",
        "运镜": "",  # not yet detected; placeholder
        "时长(s)": round(shot.get("end_time", 0) - shot.get("start_time", 0), 2),
        "画面主体描述": ", ".join(obj_classes) or "—",
        "行为": "/".join(behaviors) if behaviors else "",
        "犬种/主体": "狗" if has_dog else ("人物" if has_person else "产品"),
        "是否含人": "是" if has_person else "否",
        "是否含LOGO": "",  # future: OCR
        "适用类型": applicable_types_str,
        "已用次数": 0,
        "存储路径": material.get("file_path", ""),
        "画质等级": shot.get("quality_grade") or "",
        "备注": "已废片" if shot.get("is_rejected") else "",
        "hook_score": round(shot_scores.get("hook_score", 0), 2) if shot_scores else "",
        "evidence_score": round(shot_scores.get("evidence_score", 0), 2) if shot_scores else "",
        "emotion_score": round(shot_scores.get("emotion_score", 0), 2) if shot_scores else "",
        "start_time": shot.get("start_time", 0),
        "end_time": shot.get("end_time", 0),
        "keyframe_mid": (shot.get("key_frames") or {}).get("mid", ""),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

COLUMNS = [
    "编号", "一级分类建议", "二级分类建议", "文件名",
    "景别", "运镜", "时长(s)", "画面主体描述", "行为",
    "犬种/主体", "是否含人", "是否含LOGO", "适用类型",
    "已用次数", "存储路径", "画质等级", "备注",
    "hook_score", "evidence_score", "emotion_score",
    "start_time", "end_time", "keyframe_mid",
]


def export_batch(
    batch_id: str,
    data_root: Path,
    exports_root: Path | None = None,
    include_rejected: bool = False,
) -> Path:
    """
    Build index.json and index.csv for all materials in batch.

    Returns the export directory Path.
    """
    if exports_root is None:
        exports_root = data_root.parent / "exports"

    batch_dir = data_root / batch_id
    if not batch_dir.exists():
        raise FileNotFoundError(f"Batch data not found: {batch_dir}")

    rows: list[dict] = []

    for mat_dir in sorted(batch_dir.iterdir()):
        mat_file = mat_dir / "material.json"
        shots_file = mat_dir / "shots.json"
        labels_file = mat_dir / "labels.json"
        scores_file = mat_dir / "scores.json"

        if not mat_file.exists() or not shots_file.exists():
            continue

        material = json.loads(mat_file.read_text())
        shots = json.loads(shots_file.read_text())
        all_labels = json.loads(labels_file.read_text()) if labels_file.exists() else []
        all_scores = json.loads(scores_file.read_text()) if scores_file.exists() else []

        # Build shot → scores lookup
        scores_by_shot: dict[str, dict] = {s["shot_id"]: s for s in all_scores if "shot_id" in s}

        for shot in shots:
            if not include_rejected and shot.get("is_rejected"):
                continue
            shot_labels = [lb for lb in all_labels if lb.get("shot_id") == shot["id"]]
            shot_scores = scores_by_shot.get(shot["id"])
            rows.append(_build_row(material, shot, shot_labels, shot_scores))

    # Write outputs
    out_dir = exports_root / batch_id
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "index.json"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2))

    csv_path = out_dir / "index.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return out_dir
