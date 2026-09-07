"""L1 vision tagging: object detection, shot scale, quality grade."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from providers.vision.yolo_provider import YoloProvider
from services.subtitle_detect import detect_subtitle
from providers.vision.shot_scale import estimate_shot_scale
from providers.vision.quality import estimate_quality_grade
from providers.vision.frame_features import (
    estimate_lighting,
    estimate_camera_move,
    subject_layout,
)
from services.config import anchor_root, load_config, resolve_config_path
from services.paths import ensure_material_dir, material_id, resolve_stored_path
from services.taxonomy import load_taxonomy


def _lb(shot_id: str, label_type: str, value, conf: float, source: str = "rule") -> dict:
    return {
        "id": uuid.uuid4().hex[:12],
        "shot_id": shot_id,
        "layer": "l1",
        "label_type": label_type,
        "label_value": value,
        "source": source,
        "confidence": round(float(conf), 4),
    }


def tag_l1(
    video_path: Path,
    data_root: Path | None = None,
    batch_id: str = "default",
    config_path: Path | None = None,
    mat_id: str | None = None,
) -> Path:
    """
    Run L1 visual tagging on each shot's keyframes.

    Emits business-aligned L1 dimensions:
      object_detection, shot_scale, quality_grade, camera_move, lighting,
      has_person, has_dog, has_product, has_bowl, subject_layout,
      dog_breed (未知 unless detector provides), fur_color (未知),
      has_logo (启发式占位).
    """
    cfg = load_config(config_path)
    tax = load_taxonomy()
    if data_root is None:
        data_root = resolve_config_path(cfg["data_root"])
    if mat_id is None:
        mat_id = material_id(video_path, anchor_root(cfg))

    mat_dir = ensure_material_dir(data_root, batch_id, mat_id)
    shots_path = mat_dir / "shots.json"
    labels_path = mat_dir / "labels.json"
    ls_path = mat_dir / "layer_status.json"

    shots: list[dict] = json.loads(shots_path.read_text()) if shots_path.exists() else []
    existing_labels: list[dict] = (
        json.loads(labels_path.read_text()) if labels_path.exists() else []
    )

    weights = Path(cfg["providers"]["vision"]["yolo_weights"])
    if not weights.is_absolute():
        weights = Path(__file__).resolve().parents[1] / weights
    provider = YoloProvider(weights_path=weights)

    new_labels: list[dict] = []
    updated_shots: list[dict] = []
    product_like = tax.product_like_classes() or {
        "bottle", "cup", "bowl", "book", "cell phone", "laptop",
    }

    for shot in shots:
        shot_id = shot["id"]
        # Keyframes may be stored relative to the workspace anchor
        anchor = anchor_root(cfg)
        kfs = {
            k: resolve_stored_path(v, anchor)
            for k, v in (shot.get("key_frames") or {}).items() if v
        }
        primary_kf = kfs.get("mid") or kfs.get("start")
        start_kf = kfs.get("start")
        end_kf = kfs.get("end")

        detections: list[dict] = []
        if primary_kf and Path(primary_kf).exists():
            detections = provider.detect(Path(primary_kf))

        classes = {d.get("class_name") for d in detections}
        has_dog = "dog" in classes or "cat" in classes
        has_person = "person" in classes
        has_bowl = "bowl" in classes
        has_product = bool(classes & product_like) or has_bowl

        # Per-keyframe object classes (start/mid/end) — feeding temporal
        # behavior rules in L2 (eating persistence, subject co-occurrence).
        kf_objects: dict[str, list[str]] = {}
        for kf_label, kf in (("start", start_kf), ("mid", primary_kf), ("end", end_kf)):
            if kf and Path(kf).exists():
                kf_objects[kf_label] = (
                    sorted(classes) if kf_label == "mid"
                    else sorted({d.get("class_name") for d in provider.detect(Path(kf))})
                )

        for det in detections:
            new_labels.append(_lb(
                shot_id, "object_detection", det, det["confidence"],
                "model" if provider.available else "rule",
            ))

        scale, scale_conf = estimate_shot_scale(detections)
        new_labels.append(_lb(shot_id, "shot_scale", scale, scale_conf if scale != "未知" else 0.0))

        grade, q_score = "?", 0.0
        if primary_kf and Path(primary_kf).exists():
            grade, q_score = estimate_quality_grade(Path(primary_kf))
        new_labels.append(_lb(
            shot_id, "quality_grade", grade,
            min(1.0, q_score / 500) if q_score > 0 else 0.0,
        ))

        cam, cam_conf = estimate_camera_move(
            Path(start_kf) if start_kf else None,
            Path(end_kf) if end_kf else None,
        )
        new_labels.append(_lb(shot_id, "camera_move", cam, cam_conf))

        if primary_kf and Path(primary_kf).exists():
            lighting, light_conf, light_metrics = estimate_lighting(Path(primary_kf))
        else:
            lighting, light_conf, light_metrics = "未知", 0.0, {}
        new_labels.append(_lb(shot_id, "lighting", lighting, light_conf))
        if light_metrics:
            new_labels.append(_lb(shot_id, "lighting_metrics", light_metrics, light_conf))

        layout = subject_layout(detections)
        new_labels.append(_lb(shot_id, "subject_layout", layout, 0.7 if detections else 0.2))
        new_labels.append(_lb(shot_id, "subject_count", layout["subject_count"], 0.7 if detections else 0.3))
        new_labels.append(_lb(shot_id, "has_person", "是" if has_person else "否", 0.8 if provider.available else 0.35))
        new_labels.append(_lb(shot_id, "has_dog", "是" if has_dog else "否", 0.8 if provider.available else 0.35))
        new_labels.append(_lb(shot_id, "has_product", "是" if has_product else "否", 0.55 if provider.available else 0.25))
        new_labels.append(_lb(shot_id, "has_bowl", "是" if has_bowl else "否", 0.6 if provider.available else 0.25))
        # Breed / fur / logo need specialized models or OCR — emit placeholders from taxonomy
        breed_vals = tax.values("dog_breed")
        breed_default = "其他" if "其他" in breed_vals else (breed_vals[0] if breed_vals else "其他")
        breed_none = "无" if "无" in breed_vals else breed_default
        fur_vals = tax.values("fur_color")
        fur_unknown = "未知" if "未知" in fur_vals else (fur_vals[0] if fur_vals else "未知")
        fur_none = "无" if "无" in fur_vals else fur_unknown
        logo_vals = tax.values("has_logo") or tax.values("yes_no_unknown")
        logo_unknown = "未知" if "未知" in logo_vals else (logo_vals[0] if logo_vals else "未知")
        new_labels.append(_lb(shot_id, "dog_breed", breed_default if has_dog else breed_none, 0.2 if has_dog else 0.5))
        new_labels.append(_lb(shot_id, "fur_color", fur_unknown if has_dog else fur_none, 0.15 if has_dog else 0.5))
        new_labels.append(_lb(shot_id, "has_logo", logo_unknown, 0.1))

        # Burned-in subtitle detection on the mid keyframe (P0-1 backlog):
        # 底部字幕带边缘密度 vs 中部 —— 广告成片普遍自带花字
        has_sub, sub_pos, sub_conf = False, "无", 0.0
        if primary_kf and Path(primary_kf).exists():
            has_sub, sub_pos, sub_conf = detect_subtitle(primary_kf)
        new_labels.append(_lb(shot_id, "has_subtitle", "是" if has_sub else "否", max(0.5, sub_conf)))
        new_labels.append(_lb(shot_id, "subtitle_position", sub_pos if has_sub else "无", max(0.5, sub_conf)))

        duration = round(float(shot.get("end_time", 0)) - float(shot.get("start_time", 0)), 2)
        new_labels.append(_lb(shot_id, "duration", duration, 1.0, "rule"))

        shot = dict(shot)
        shot["quality_grade"] = grade
        shot["kf_objects"] = kf_objects
        updated_shots.append(shot)

    labels_path.write_text(
        json.dumps(existing_labels + new_labels, ensure_ascii=False, indent=2)
    )
    shots_path.write_text(json.dumps(updated_shots, ensure_ascii=False, indent=2))

    try:
        ls = json.loads(ls_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        ls = {}
    ls["l1"] = "done"
    ls_path.write_text(json.dumps(ls, indent=2))

    return mat_dir
