"""L1 vision tagging: object detection, shot scale, quality grade."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from providers.vision.yolo_provider import YoloProvider
from providers.vision.shot_scale import estimate_shot_scale
from providers.vision.quality import estimate_quality_grade
from services.config import load_config
from services.paths import ensure_material_dir, material_id


def tag_l1(
    video_path: Path,
    data_root: Path | None = None,
    batch_id: str = "default",
    config_path: Path | None = None,
    mat_id: str | None = None,
) -> Path:
    """
    Run L1 visual tagging on each shot's keyframes.

    Appends labels to labels.json; updates quality_grade in shots.json;
    updates layer_status.json with {"l1": "done"}.
    Returns material directory.
    """
    cfg = load_config(config_path)
    if data_root is None:
        data_root = Path(cfg["data_root"])
    if mat_id is None:
        mat_id = material_id(video_path)

    mat_dir = ensure_material_dir(data_root, batch_id, mat_id)
    shots_path = mat_dir / "shots.json"
    labels_path = mat_dir / "labels.json"
    ls_path = mat_dir / "layer_status.json"

    shots: list[dict] = json.loads(shots_path.read_text()) if shots_path.exists() else []
    existing_labels: list[dict] = (
        json.loads(labels_path.read_text()) if labels_path.exists() else []
    )

    weights = Path(cfg["providers"]["vision"]["yolo_weights"])
    provider = YoloProvider(weights_path=weights)

    new_labels: list[dict] = []
    updated_shots: list[dict] = []

    for shot in shots:
        shot_id = shot["id"]
        kf_paths = shot.get("key_frames", {})
        # Use mid-frame as primary; fallback to start
        primary_kf = kf_paths.get("mid") or kf_paths.get("start")

        detections: list[dict] = []
        if primary_kf and Path(primary_kf).exists():
            detections = provider.detect(Path(primary_kf))

        # --- Object detection labels ---
        for det in detections:
            new_labels.append({
                "id": uuid.uuid4().hex[:12],
                "shot_id": shot_id,
                "layer": "l1",
                "label_type": "object_detection",
                "label_value": det,
                "source": "model" if provider.available else "rule",
                "confidence": det["confidence"],
            })

        # --- Shot scale ---
        scale, scale_conf = estimate_shot_scale(detections)
        new_labels.append({
            "id": uuid.uuid4().hex[:12],
            "shot_id": shot_id,
            "layer": "l1",
            "label_type": "shot_scale",
            "label_value": scale,
            "source": "rule",
            "confidence": scale_conf if scale != "未知" else 0.0,
        })

        # --- Quality grade ---
        grade, q_score = "?", 0.0
        if primary_kf and Path(primary_kf).exists():
            grade, q_score = estimate_quality_grade(Path(primary_kf))
        new_labels.append({
            "id": uuid.uuid4().hex[:12],
            "shot_id": shot_id,
            "layer": "l1",
            "label_type": "quality_grade",
            "label_value": grade,
            "source": "rule",
            "confidence": min(1.0, q_score / 500) if q_score > 0 else 0.0,
        })

        shot = dict(shot)
        shot["quality_grade"] = grade
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
