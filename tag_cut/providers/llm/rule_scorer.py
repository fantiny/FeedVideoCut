"""
Rule-based L3–L6 scorer — expanded to business label taxonomy.

Produces (per shot):
  L3  relation_hint, relation_chain, behavior_chain, subject_role
  L4  applicable_types, category_code, emotion, emotion_intensity,
      commercial_evidence, hook_role, content_intent
  L5  edit_value (expanded), usable_duration, platform_fit
  L6  compliance (expanded)
  capability_scores — hook/evidence/emotion/product/conversion/ending/transition/trust
"""
from __future__ import annotations

from services.taxonomy import load_taxonomy


def _filter_allowed(values: list[str], allowed: list[str]) -> list[str]:
    if not allowed:
        return values
    keep = [v for v in values if v in allowed]
    return keep if keep else values


def _get_labels(labels: list[dict], layer: str, label_type: str) -> list[dict]:
    return [lb for lb in labels if lb.get("layer") == layer and lb.get("label_type") == label_type]


def _first_value(labels: list[dict], layer: str, label_type: str, default=None):
    items = _get_labels(labels, layer, label_type)
    return items[0].get("label_value") if items else default


def _has_event(labels: list[dict], event_value: str) -> bool:
    return any(
        lb.get("label_value") == event_value
        for lb in labels
        if lb.get("layer") == "l2" and lb.get("label_type") in ("audio_event", "behavior")
    )


def _yes(labels: list[dict], label_type: str) -> bool:
    return _first_value(labels, "l1", label_type) == "是"


def _behaviors(labels: list[dict]) -> list[str]:
    return [
        str(lb.get("label_value"))
        for lb in labels
        if lb.get("layer") == "l2" and lb.get("label_type") == "behavior"
    ]


def _audio_events(labels: list[dict]) -> list[str]:
    return [
        str(lb.get("label_value"))
        for lb in labels
        if lb.get("layer") == "l2" and lb.get("label_type") == "audio_event"
    ]


def _mk(shot_id: str, layer: str, label_type: str, value, conf: float) -> dict:
    return {
        "shot_id": shot_id,
        "layer": layer,
        "label_type": label_type,
        "label_value": value,
        "source": "rule",
        "confidence": round(float(conf), 4),
    }


def score_shot(
    shot: dict,
    labels: list[dict],
) -> tuple[list[dict], dict]:
    tax = load_taxonomy()
    shot_id = shot["id"]
    duration = float(shot.get("end_time", 0)) - float(shot.get("start_time", 0))
    quality_grade = shot.get("quality_grade") or _first_value(labels, "l1", "quality_grade", "?")
    shot_labels = [lb for lb in labels if lb.get("shot_id") == shot_id]

    has_dog = _yes(shot_labels, "has_dog") or any(
        isinstance(lb.get("label_value"), dict) and lb["label_value"].get("class_name") == "dog"
        for lb in shot_labels if lb.get("label_type") == "object_detection"
    )
    has_person = _yes(shot_labels, "has_person") or any(
        isinstance(lb.get("label_value"), dict) and lb["label_value"].get("class_name") == "person"
        for lb in shot_labels if lb.get("label_type") == "object_detection"
    )
    has_product = _yes(shot_labels, "has_product")
    has_bowl = _yes(shot_labels, "has_bowl")

    scale = _first_value(shot_labels, "l1", "shot_scale", "未知")
    camera = _first_value(shot_labels, "l1", "camera_move", "未知")
    lighting = _first_value(shot_labels, "l1", "lighting", "未知")
    layout = _first_value(shot_labels, "l1", "subject_layout", {}) or {}
    is_closeup = scale in tax.closeup_scales()

    behaviors = _behaviors(shot_labels)
    audio = _audio_events(shot_labels)
    has_speech = "speech" in audio or "人物讲解" in behaviors
    has_chew = "chew" in audio or "第一口" in behaviors or "大口进食" in behaviors
    has_eating = "大口进食" in behaviors
    has_lick = "舔碗" in behaviors or "lick" in audio
    # P0-2: temporal vision signal — animal + food cues across ≥2 keyframes
    # (audio-only chew events were too rare, so eating evidence never landed)
    kf_objects = shot.get("kf_objects") or {}
    _animal, _food = {"dog", "cat"}, {"bowl", "carrot", "broccoli", "banana",
                                      "orange", "apple", "cup"}
    _ak = sum(1 for o in kf_objects.values() if _animal & set(o))
    _fk = sum(1 for o in kf_objects.values() if _food & set(o))
    has_vision_eating = min(_ak, _fk) >= 2
    has_chew = has_chew or has_vision_eating
    has_eating = has_eating or has_vision_eating
    has_first_bite = "第一口" in behaviors
    has_approach = "凑近闻" in behaviors
    has_wag = "摇尾" in behaviors
    has_wait = "等待投喂" in behaviors
    has_feed = "递碗投喂" in behaviors

    new_labels: list[dict] = []

    # ----- L3 relations & chains -----
    relation = None
    chain: list[str] = []
    if has_feed or (has_person and has_bowl):
        relation = "人物→狗/碗"
        chain = ["递碗", "靠近", "进食"]
    elif has_person and has_dog and has_speech:
        relation = "人物→狗"
        chain = ["讲解", "互动"]
    elif has_dog and has_bowl and (has_eating or has_lick or has_chew):
        relation = "狗→碗/产品"
        chain = [b for b in ["凑近闻", "第一口", "大口进食", "舔碗"] if b in behaviors] or ["进食"]
    elif has_dog and has_product:
        relation = "狗→产品"
        chain = behaviors[:3] or ["互动"]
    elif has_person and has_product:
        relation = "人物→产品"
        chain = ["展示"]

    if relation:
        new_labels.append(_mk(shot_id, "l3", "relation_hint", relation, 0.62))
    if chain:
        new_labels.append(_mk(shot_id, "l3", "behavior_chain", chain, 0.55))
        new_labels.append(_mk(shot_id, "l3", "relation_chain", {
            "relation": relation or "未知",
            "steps": chain,
        }, 0.5))

    if has_dog and not has_person:
        role = "狗主体"
    elif has_person and not has_dog:
        role = "人物主体"
    elif has_person and has_dog:
        role = "人物+狗"
    elif has_product:
        role = "产品主体"
    else:
        role = "场景"
    role = tax.normalize("subject_role", role)
    new_labels.append(_mk(shot_id, "l3", "subject_role", role, 0.6))

    # ----- L4 content / commercial / emotion -----
    types: list[str] = []
    if has_first_bite or has_eating or has_lick or (is_closeup and has_dog):
        types.append("种草")
    if has_speech or (has_person and duration >= 2.0):
        types.extend(["科普", "分享"])
    if has_product and (is_closeup or has_speech):
        types.append("营销")
    # dedupe preserve order
    seen = set()
    types = [t for t in types if not (t in seen or seen.add(t))]
    if not types:
        types = ["通用"]
    types = _filter_allowed(types, tax.values("applicable_types"))
    new_labels.append(_mk(shot_id, "l4", "applicable_types", types, 0.58))

    if has_dog and (has_eating or has_lick or has_first_bite or has_approach):
        category = "V03_狗狗进食"
    elif has_person and has_speech:
        category = "V04_人物出镜"
    elif has_product and is_closeup:
        category = "V01_产品特写"
    elif has_person and not has_speech:
        category = "V02_制作工艺"
    else:
        category = tax.default("category_code", "V99_待分类")
    category = tax.normalize("category_code", category)
    new_labels.append(_mk(shot_id, "l4", "category_code", category, 0.55))

    # Emotion (multi-label evidence based)
    emotions: list[str] = []
    intensity = "中"
    if has_wag or has_first_bite:
        emotions.append("兴奋")
        intensity = "高"
    if has_approach:
        emotions.append("期待")
    if has_eating or has_lick:
        emotions.append("满足")
    if is_closeup and has_dog and not has_speech:
        emotions.append("治愈")
    if has_speech:
        emotions.append("平静")
    if not emotions:
        emotions = ["平静" if duration > 2 else "未知"]
        intensity = "低"
    emotions = _filter_allowed(emotions, tax.values("emotion"))
    intensity = tax.normalize("emotion_intensity", intensity)
    new_labels.append(_mk(shot_id, "l4", "emotion", emotions, 0.5))
    new_labels.append(_mk(shot_id, "l4", "emotion_intensity", intensity, 0.5))

    commercial = {
        "product_presence": has_product or has_bowl,
        "product_clarity": bool(is_closeup and (has_product or has_bowl)),
        "ingredient_evidence": bool(is_closeup and has_product and not has_dog),
        "process_evidence": bool(has_person and not has_dog and camera in ("固定", "推", "微距")),
        "eating_evidence": bool(has_chew or has_eating or has_lick or (has_dog and has_bowl)),
        "price_signal": False,  # needs OCR
        "gift_signal": False,
        "store_signal": False,
        "packaging_version": "未知",
    }
    new_labels.append(_mk(shot_id, "l4", "commercial_evidence", commercial, 0.45))

    if has_first_bite or (is_closeup and has_dog and duration <= 1.5):
        hook_role = "黄金3秒钩子"
    elif commercial["ingredient_evidence"] or commercial["process_evidence"]:
        hook_role = "证据段"
    elif has_speech:
        hook_role = "讲解段"
    elif has_lick or has_wag:
        hook_role = "结尾/情绪段"
    else:
        hook_role = "过渡/填充"
    hook_role = tax.normalize("hook_role", hook_role)
    new_labels.append(_mk(shot_id, "l4", "hook_role", hook_role, 0.55))

    if "种草" in types:
        intent = "视觉吸引+食欲"
    elif "科普" in types:
        intent = "知识解释+信任"
    elif "营销" in types:
        intent = "转化推动"
    else:
        intent = "通用素材"
    new_labels.append(_mk(shot_id, "l4", "content_intent", intent, 0.5))

    # ----- L5 editability -----
    usable = {
        "raw_duration": round(duration, 2),
        "recommended_in": 0.0,
        "recommended_out": round(min(duration, 2.5), 2),
        "fits_sop_shot": 0.8 <= duration <= 2.5,
        "needs_trim": duration > 2.5,
        "too_short": duration < 0.8,
    }
    edit = {
        "loop_value": bool(has_lick or (is_closeup and not has_speech)),
        "crop_safe": quality_grade in ("A", "B") and bool(layout.get("safe_zone_ok", True)),
        "slow_mo_value": bool(has_first_bite and is_closeup),
        "short_clip": duration < 2.0,
        "subject_position": layout.get("position", "未知"),
        "subject_ratio": layout.get("largest_ratio", 0.0),
        "edge_risk": bool(layout.get("edge_risk", False)),
        "safe_zone_ok": bool(layout.get("safe_zone_ok", True)),
        "stability_ok": camera in ("固定", "微距", "推") and quality_grade in ("A", "B"),
        "vertical_ready": True,  # pet ads assumed vertical input
        "subtitle_safe": bool(layout.get("safe_zone_ok", True)),
        "camera_move": camera,
        "lighting": lighting,
    }
    new_labels.append(_mk(shot_id, "l5", "edit_value", edit, 0.55))
    new_labels.append(_mk(shot_id, "l5", "usable_duration", usable, 0.7))
    new_labels.append(_mk(shot_id, "l5", "platform_fit", {
        "douyin_safe_zone": edit["subtitle_safe"],
        "asmr_audio": bool(has_chew or has_lick),
        "hook_ready": hook_role == "黄金3秒钩子",
    }, 0.5))

    # ----- L6 compliance -----
    compliance = {
        "authorisation_required": has_person,
        "portrait_risk": "高" if has_person else "低",
        "auth_status": "待确认" if has_person else "自有(默认)",
        "valid_until": "长期",
        "claim_risk": "中" if has_speech else "低",
        "price_validity_needed": False,
        "activity_validity_needed": False,
        "logo_version_check": _first_value(shot_labels, "l1", "has_logo", "未知") != "否",
        "notes": "含人物出镜需核对肖像授权" if has_person else "",
    }
    new_labels.append(_mk(shot_id, "l6", "compliance", compliance, 0.55))

    # ----- capability scores -----
    scores = {
        "shot_id": shot_id,
        "hook_score": round(
            0.9 if has_first_bite and is_closeup else
            0.75 if (is_closeup and has_dog and duration <= 1.5) else
            0.55 if is_closeup else 0.25, 2),
        "evidence_score": round(
            0.85 if commercial["ingredient_evidence"] or commercial["process_evidence"] else
            0.7 if has_chew or has_eating else 0.2, 2),
        "emotion_score": round(
            0.85 if "兴奋" in emotions or "满足" in emotions else
            0.6 if has_dog else 0.25, 2),
        "product_score": round(
            0.8 if commercial["product_clarity"] else
            0.5 if has_product or has_bowl else 0.15, 2),
        "conversion_score": round(
            0.55 if has_speech and has_product else
            0.35 if has_speech else 0.15, 2),
        "ending_score": round(0.85 if has_lick or has_wag else 0.3, 2),
        "transition_score": round(
            0.7 if duration < 1.2 and camera in ("推", "摇", "手持") else
            0.5 if duration < 1.5 else 0.35, 2),
        "trust_score": round(
            0.8 if commercial["process_evidence"] or (has_speech and has_person) else
            0.45 if has_speech else 0.25, 2),
    }

    return new_labels, scores
