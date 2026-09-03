"""
Rule-based L3–L6 scorer.

Derives higher-level labels from L1/L2 labels using SOP business rules.
Produces:
  L3  relation_hint     — e.g. "人物投喂" when speech + chew present
  L4  applicable_types  — 种草/科普/分享/营销 suitability flags
  L5  edit_value        — loop_value, crop_safe, slow_mo_value
  L6  compliance        — placeholder; authorisation_required flag
  capability_scores     — hook/evidence/emotion/product/conversion/ending/transition/trust
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_labels(labels: list[dict], layer: str, label_type: str) -> list[dict]:
    return [lb for lb in labels if lb.get("layer") == layer and lb.get("label_type") == label_type]


def _has_event(labels: list[dict], event_value: str) -> bool:
    return any(
        lb.get("label_value") == event_value
        for lb in labels
        if lb.get("layer") == "l2" and lb.get("label_type") in ("audio_event", "behavior")
    )


def _max_confidence(items: list[dict]) -> float:
    if not items:
        return 0.0
    return max(it.get("confidence", 0.0) for it in items)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_shot(
    shot: dict,
    labels: list[dict],  # all labels for this shot
) -> tuple[list[dict], dict]:
    """
    Return (new_labels, capability_scores) derived from existing L1/L2 labels.
    new_labels have layer l3–l6.
    """
    shot_id = shot["id"]
    duration = shot.get("end_time", 0) - shot.get("start_time", 0)
    quality_grade = shot.get("quality_grade", "?")

    shot_labels = [lb for lb in labels if lb.get("shot_id") == shot_id]

    # Convenience lookups
    has_dog = any(
        lb.get("label_value", {}).get("class_name") == "dog"
        for lb in shot_labels
        if lb.get("label_type") == "object_detection"
    )
    has_person = any(
        lb.get("label_value", {}).get("class_name") == "person"
        for lb in shot_labels
        if lb.get("label_type") == "object_detection"
    )
    scale_labels = _get_labels(shot_labels, "l1", "shot_scale")
    scale = scale_labels[0]["label_value"] if scale_labels else "未知"
    is_closeup = scale in ("大特写", "特写")

    has_speech = _has_event(shot_labels, "speech")
    has_chew = _has_event(shot_labels, "chew") or _has_event(shot_labels, "第一口") or _has_event(shot_labels, "大口进食")
    has_eating = _has_event(shot_labels, "大口进食")
    has_lick = _has_event(shot_labels, "舔碗")
    has_first_bite = _has_event(shot_labels, "第一口")

    new_labels: list[dict] = []

    # --- L3: relation hint ---
    relation: str | None = None
    if has_speech and (has_chew or has_dog):
        relation = "人物投喂"
    elif has_dog and has_eating:
        relation = "狗狗进食"
    elif has_dog and has_lick:
        relation = "狗狗舔碗"
    if relation:
        new_labels.append({
            "shot_id": shot_id, "layer": "l3",
            "label_type": "relation_hint", "label_value": relation,
            "source": "rule", "confidence": 0.6,
        })

    # --- L4: applicable video types ---
    types: list[str] = []
    if has_first_bite or has_eating or is_closeup:
        types.append("种草")
    if has_speech:
        types += ["科普", "分享"]
    if not types:
        types = ["通用"]
    new_labels.append({
        "shot_id": shot_id, "layer": "l4",
        "label_type": "applicable_types", "label_value": types,
        "source": "rule", "confidence": 0.55,
    })

    # --- L5: edit value ---
    edit = {
        "loop_value": has_lick or (is_closeup and not has_speech),
        "crop_safe": quality_grade in ("A", "B"),
        "slow_mo_value": has_first_bite and is_closeup,
        "short_clip": duration < 2.0,
    }
    new_labels.append({
        "shot_id": shot_id, "layer": "l5",
        "label_type": "edit_value", "label_value": edit,
        "source": "rule", "confidence": 0.5,
    })

    # --- L6: compliance placeholder ---
    new_labels.append({
        "shot_id": shot_id, "layer": "l6",
        "label_type": "compliance", "label_value": {"authorisation_required": has_person},
        "source": "rule", "confidence": 0.5,
    })

    # --- Capability scores ---
    scores: dict = {
        "shot_id": shot_id,
        "hook_score": round(0.8 if has_first_bite and is_closeup else
                            0.6 if is_closeup else 0.3, 2),
        "evidence_score": round(0.7 if has_chew or has_eating else 0.2, 2),
        "emotion_score": round(0.75 if has_eating and has_dog else
                               0.5 if has_dog else 0.2, 2),
        "product_score": round(0.5 if is_closeup else 0.2, 2),
        "conversion_score": round(0.4 if has_speech else 0.15, 2),
        "ending_score": round(0.8 if has_lick else 0.3, 2),
        "transition_score": round(0.6 if duration < 1.5 else 0.4, 2),
        "trust_score": round(0.7 if has_speech else 0.3, 2),
    }

    return new_labels, scores
