"""
L3–L6 tagging pipeline.

1. Rule scorer  → relation hints, applicable types, edit value, compliance, capability scores
2. Cloud VLM    → optional enhancement (default off)

Writes:
  labels.json  (appended L3–L6 labels)
  scores.json  (per-shot capability scores)
  layer_status.json  {"l3_l6": "done"}
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from providers.llm.rule_scorer import score_shot
from providers.llm.cloud_vlm import CloudVLMProvider
from services.config import anchor_root, load_config, resolve_config_path
from services.paths import ensure_material_dir, material_id
from services.semantic import compose_semantic_desc, refine_semantic_batch, resolve_semantic_llm


def tag_l3_l6(
    video_path: Path,
    data_root: Path | None = None,
    batch_id: str = "default",
    config_path: Path | None = None,
    mat_id: str | None = None,
) -> Path:
    """
    Run L3–L6 scoring for all shots of a material.
    Returns material directory.
    """
    cfg = load_config(config_path)
    if data_root is None:
        data_root = resolve_config_path(cfg["data_root"])
    if mat_id is None:
        mat_id = material_id(video_path, anchor_root(cfg))

    mat_dir = ensure_material_dir(data_root, batch_id, mat_id)
    shots_path = mat_dir / "shots.json"
    labels_path = mat_dir / "labels.json"
    scores_path = mat_dir / "scores.json"
    ls_path = mat_dir / "layer_status.json"

    shots: list[dict] = json.loads(shots_path.read_text()) if shots_path.exists() else []
    all_labels: list[dict] = json.loads(labels_path.read_text()) if labels_path.exists() else []
    existing_scores: list[dict] = json.loads(scores_path.read_text()) if scores_path.exists() else []

    cloud_provider = CloudVLMProvider(cfg)

    new_labels: list[dict] = []
    new_scores: list[dict] = []
    semantic_items: list[dict] = []  # (P1-5) rule-composed 语义描述, refined by LLM below

    for shot in shots:
        shot_id = shot["id"]
        shot_labels = [lb for lb in all_labels if lb.get("shot_id") == shot_id]

        # Rule-based L3–L6 labels + scores
        rule_labels, cap_scores = score_shot(shot, all_labels)

        # Assign IDs to rule labels
        for lb in rule_labels:
            lb.setdefault("id", uuid.uuid4().hex[:12])

        new_labels.extend(rule_labels)
        new_scores.append(cap_scores)

        # 语义描述（规则组合）：主体 + 行为动作短语 + 分类
        behaviors = [
            str(lb.get("label_value"))
            for lb in shot_labels + rule_labels
            if lb.get("layer") == "l2" and lb.get("label_type") == "behavior"
        ]
        has_dog = any(
            lb.get("layer") == "l1" and lb.get("label_type") == "has_dog" and lb.get("label_value") == "是"
            for lb in shot_labels
        )
        has_person = any(
            lb.get("layer") == "l1" and lb.get("label_type") == "has_person" and lb.get("label_value") == "是"
            for lb in shot_labels
        )
        has_product = any(
            lb.get("layer") == "l1" and lb.get("label_type") == "has_product" and lb.get("label_value") == "是"
            for lb in shot_labels
        )
        objects = sorted({
            str(v.get("class_name"))
            for lb in shot_labels
            if lb.get("label_type") == "object_detection" and isinstance(lb.get("label_value"), dict)
            for v in [lb["label_value"]] if v.get("class_name")
        })
        category = next(
            (str(lb.get("label_value")) for lb in rule_labels
             if lb.get("layer") == "l4" and lb.get("label_type") == "category_code"),
            "",
        )
        rule_desc = compose_semantic_desc(
            has_dog=has_dog, has_person=has_person, has_product=has_product,
            behaviors=behaviors, category=category, objects=objects,
            shot_scale=str(shot.get("shot_scale") or ""),
        )
        semantic_items.append({
            "shot_id": shot_id,
            "rule_desc": rule_desc,
            "objects": objects,
            "behaviors": behaviors,
            "category": category,
        })
        new_labels.append({
            "id": uuid.uuid4().hex[:12],
            "shot_id": shot_id,
            "layer": "l3",
            "label_type": "semantic_desc",
            "label_value": rule_desc,
            "source": "rule",
            "confidence": 0.5,
        })

        # Optional cloud VLM enhancement
        if cloud_provider.enabled:
            kf_paths = [
                Path(p) for p in shot.get("key_frames", {}).values() if p
            ]
            vlm_labels = cloud_provider.enhance(
                shot_id=shot_id,
                keyframe_paths=kf_paths,
                existing_labels=shot_labels + rule_labels,
            )
            for lb in vlm_labels:
                lb.setdefault("id", uuid.uuid4().hex[:12])
            new_labels.extend(vlm_labels)

    # 语义描述 LLM 批量精修（可选）：改写失败时保留规则描述
    llm = resolve_semantic_llm(cfg)
    if llm and semantic_items:
        refined = refine_semantic_batch(semantic_items, llm)
        if refined:
            for lb in new_labels:
                if lb.get("layer") == "l3" and lb.get("label_type") == "semantic_desc":
                    better = refined.get(str(lb.get("shot_id")))
                    if better:
                        lb["label_value"] = better
                        lb["source"] = "llm"
                        lb["confidence"] = 0.8

    labels_path.write_text(
        json.dumps(all_labels + new_labels, ensure_ascii=False, indent=2)
    )
    scores_path.write_text(
        json.dumps(existing_scores + new_scores, ensure_ascii=False, indent=2)
    )

    try:
        ls = json.loads(ls_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        ls = {}
    ls["l3_l6"] = "done"
    ls_path.write_text(json.dumps(ls, indent=2))

    return mat_dir
