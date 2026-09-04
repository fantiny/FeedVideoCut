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


def _fmt_list(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "/".join(str(v) for v in value)
    return str(value)


def _build_row(material: dict, shot: dict, shot_labels: list[dict], shot_scores: dict | None) -> dict:
    obj_classes = _objects_of(shot_labels)
    has_dog = _first_label(shot_labels, "l1", "has_dog") == "是" or "dog" in obj_classes
    has_person = _first_label(shot_labels, "l1", "has_person") == "是" or "person" in obj_classes
    has_product = _first_label(shot_labels, "l1", "has_product") == "是"

    category = _first_label(shot_labels, "l4", "category_code")
    if not category:
        category = (
            "V03_狗狗进食" if has_dog else
            "V04_人物出镜" if has_person else
            "V01_产品特写" if has_product else
            "V99_待分类"
        )

    applicable_types_str = _fmt_list(_first_label(shot_labels, "l4", "applicable_types") or [])
    emotion_str = _fmt_list(_first_label(shot_labels, "l4", "emotion") or [])
    behaviors = [
        str(lb["label_value"])
        for lb in shot_labels
        if lb.get("layer") == "l2" and lb.get("label_type") == "behavior"
    ]
    commercial = _first_label(shot_labels, "l4", "commercial_evidence") or {}
    compliance = _first_label(shot_labels, "l6", "compliance") or {}
    breed = _first_label(shot_labels, "l1", "dog_breed")
    if breed in (None, "无", "其他"):
        breed_subject = "狗" if has_dog else ("人物" if has_person else "产品")
    else:
        breed_subject = str(breed)

    return {
        "编号": shot["id"],
        "一级分类建议": "01_视频素材",
        "二级分类建议": category,
        "文件名": material.get("file_name", ""),
        "景别": _first_label(shot_labels, "l1", "shot_scale") or "未知",
        "运镜": _first_label(shot_labels, "l1", "camera_move") or "未知",
        "光线": _first_label(shot_labels, "l1", "lighting") or "未知",
        "时长(s)": round(shot.get("end_time", 0) - shot.get("start_time", 0), 2),
        "画面主体描述": ", ".join(obj_classes) or "—",
        "主体角色": _first_label(shot_labels, "l3", "subject_role") or "",
        "关系": _first_label(shot_labels, "l3", "relation_hint") or "",
        "行为": "/".join(behaviors) if behaviors else "",
        "音频质感": _first_label(shot_labels, "l2", "audio_texture") or "",
        "犬种/主体": breed_subject,
        "毛色": _first_label(shot_labels, "l1", "fur_color") or "",
        "是否含人": "是" if has_person else "否",
        "是否含LOGO": _first_label(shot_labels, "l1", "has_logo") or "未知",
        "情绪": emotion_str,
        "情绪强度": _first_label(shot_labels, "l4", "emotion_intensity") or "",
        "钩子角色": _first_label(shot_labels, "l4", "hook_role") or "",
        "适用类型": applicable_types_str,
        "进食证据": "是" if commercial.get("eating_evidence") else "否",
        "产品清晰": "是" if commercial.get("product_clarity") else "否",
        "肖像风险": compliance.get("portrait_risk") or "",
        "授权状态": compliance.get("auth_status") or "",
        "已用次数": 0,
        "存储路径": material.get("file_path", ""),
        "画质等级": shot.get("quality_grade") or _first_label(shot_labels, "l1", "quality_grade") or "",
        "备注": "已废片" if shot.get("is_rejected") else (compliance.get("notes") or ""),
        "hook_score": round(shot_scores.get("hook_score", 0), 2) if shot_scores else "",
        "evidence_score": round(shot_scores.get("evidence_score", 0), 2) if shot_scores else "",
        "emotion_score": round(shot_scores.get("emotion_score", 0), 2) if shot_scores else "",
        "product_score": round(shot_scores.get("product_score", 0), 2) if shot_scores else "",
        "start_time": shot.get("start_time", 0),
        "end_time": shot.get("end_time", 0),
        "keyframe_mid": (shot.get("key_frames") or {}).get("mid", ""),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

COLUMNS = [
    "编号", "一级分类建议", "二级分类建议", "文件名",
    "景别", "运镜", "光线", "时长(s)", "画面主体描述", "主体角色", "关系", "行为", "音频质感",
    "犬种/主体", "毛色", "是否含人", "是否含LOGO",
    "情绪", "情绪强度", "钩子角色", "适用类型",
    "进食证据", "产品清晰", "肖像风险", "授权状态",
    "已用次数", "存储路径", "画质等级", "备注",
    "hook_score", "evidence_score", "emotion_score", "product_score",
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
