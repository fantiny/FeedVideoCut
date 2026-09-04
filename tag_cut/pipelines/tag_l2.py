"""
L2 tagging: audio event detection + behavior rule recognition.

Behavior rules (对齐 V03 素材库 SOP — 从 L1 主体 + 音频事件 + 时长推断):
  凑近闻 / 第一口 / 大口进食 / 舔碗 / 摇尾 / 等待投喂 /
  人物讲解 / 递碗投喂 / 抬头看镜头 / 状态镜头

Also emits:
  audio_texture  — ASMR咀嚼 / 人声讲解 / 环境音 / 静音 / 犬吠
  audio_role     — 钩子音效 / 证据音 / 旁白 / 氛围
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from providers.audio.vad_provider import detect_audio_events
from services.config import load_config
from services.paths import ensure_material_dir, material_id


def _l1_flag(labels: list[dict], shot_id: str, label_type: str) -> str | None:
    for lb in labels:
        if (
            lb.get("shot_id") == shot_id
            and lb.get("layer") == "l1"
            and lb.get("label_type") == label_type
        ):
            return lb.get("label_value")
    return None


def _infer_behaviors(
    audio_events: list[dict],
    duration: float,
    *,
    has_dog: bool = False,
    has_person: bool = False,
    has_bowl: bool = False,
    shot_scale: str | None = None,
) -> list[dict]:
    """
    Map audio events + duration + L1 subject context to V03 behavior labels.
    Returns list of behavior dicts with confidence.
    """
    event_names = {e["event"] for e in audio_events}
    behaviors: list[dict] = []
    is_closeup = shot_scale in ("大特写", "特写")

    if "speech" in event_names:
        behaviors.append({"behavior": "人物讲解", "confidence": 0.75})

    if has_person and has_bowl and has_dog and "speech" not in event_names:
        behaviors.append({"behavior": "递碗投喂", "confidence": 0.5})

    if "chew" in event_names:
        if duration < 2.0:
            behaviors.append({"behavior": "第一口", "confidence": 0.6})
        else:
            behaviors.append({"behavior": "大口进食", "confidence": 0.65})

    if "lick" in event_names:
        behaviors.append({"behavior": "舔碗", "confidence": 0.65})

    if "bark" in event_names and "speech" not in event_names:
        behaviors.append({"behavior": "摇尾", "confidence": 0.45})

    if not behaviors:
        if "silent" in event_names or "ambient" in event_names or not event_names:
            if has_dog and is_closeup and duration <= 1.2:
                behaviors.append({"behavior": "抬头看镜头", "confidence": 0.35})
            elif duration > 2.5 and has_dog and not has_person:
                behaviors.append({"behavior": "状态镜头", "confidence": 0.4})
            elif duration > 2.0:
                behaviors.append({"behavior": "等待投喂", "confidence": 0.4})
            else:
                # Default short ambient clip in pet ads ≈ approach-to-bowl
                behaviors.append({"behavior": "凑近闻", "confidence": 0.4})

    # Deduplicate by behavior name, keep highest confidence
    best: dict[str, dict] = {}
    for b in behaviors:
        name = b["behavior"]
        if name not in best or b["confidence"] > best[name]["confidence"]:
            best[name] = b
    return list(best.values())


def _audio_texture(audio_events: list[dict]) -> tuple[str, float]:
    names = {e["event"] for e in audio_events}
    if "chew" in names or "lick" in names:
        return "ASMR咀嚼", 0.65
    if "speech" in names:
        return "人声讲解", 0.75
    if "bark" in names:
        return "犬吠", 0.6
    if "silent" in names:
        return "静音", 0.7
    if "ambient" in names:
        return "环境音", 0.55
    return "未知", 0.2


def _audio_role(texture: str, duration: float) -> tuple[str, float]:
    if texture == "ASMR咀嚼" and duration < 2.0:
        return "钩子音效", 0.55
    if texture == "ASMR咀嚼":
        return "证据音", 0.55
    if texture == "人声讲解":
        return "旁白", 0.7
    if texture in ("环境音", "静音", "犬吠"):
        return "氛围", 0.5
    return "未知", 0.2


def tag_l2(
    video_path: Path,
    data_root: Path | None = None,
    batch_id: str = "default",
    config_path: Path | None = None,
    mat_id: str | None = None,
) -> Path:
    """
    Run L2 tagging: audio events + behavior inference per shot.

    Appends to labels.json; updates layer_status.json with {"l2": "done"}.
    Returns material directory.
    """
    cfg = load_config(config_path)
    if data_root is None:
        data_root = Path(cfg["data_root"])
    if mat_id is None:
        mat_id = material_id(video_path)

    audio_enabled: bool = cfg.get("providers", {}).get("audio", {}).get("enabled", True)

    mat_dir = ensure_material_dir(data_root, batch_id, mat_id)
    shots_path = mat_dir / "shots.json"
    labels_path = mat_dir / "labels.json"
    ls_path = mat_dir / "layer_status.json"

    shots: list[dict] = json.loads(shots_path.read_text()) if shots_path.exists() else []
    existing_labels: list[dict] = (
        json.loads(labels_path.read_text()) if labels_path.exists() else []
    )

    new_labels: list[dict] = []

    for shot in shots:
        shot_id = shot["id"]
        start = float(shot.get("start_time", 0))
        end = float(shot.get("end_time", start + 1))
        duration = end - start

        has_dog = _l1_flag(existing_labels, shot_id, "has_dog") == "是"
        has_person = _l1_flag(existing_labels, shot_id, "has_person") == "是"
        has_bowl = _l1_flag(existing_labels, shot_id, "has_bowl") == "是"
        shot_scale = _l1_flag(existing_labels, shot_id, "shot_scale")

        audio_events: list[dict] = []
        if audio_enabled:
            audio_events = detect_audio_events(video_path, start, end)

        for ev in audio_events:
            new_labels.append({
                "id": uuid.uuid4().hex[:12],
                "shot_id": shot_id,
                "layer": "l2",
                "label_type": "audio_event",
                "label_value": ev["event"],
                "source": ev.get("source", "rule"),
                "confidence": ev["confidence"],
            })

        texture, t_conf = _audio_texture(audio_events)
        role, r_conf = _audio_role(texture, duration)
        new_labels.append({
            "id": uuid.uuid4().hex[:12],
            "shot_id": shot_id,
            "layer": "l2",
            "label_type": "audio_texture",
            "label_value": texture,
            "source": "rule",
            "confidence": t_conf,
        })
        new_labels.append({
            "id": uuid.uuid4().hex[:12],
            "shot_id": shot_id,
            "layer": "l2",
            "label_type": "audio_role",
            "label_value": role,
            "source": "rule",
            "confidence": r_conf,
        })

        behaviors = _infer_behaviors(
            audio_events,
            duration,
            has_dog=has_dog,
            has_person=has_person,
            has_bowl=has_bowl,
            shot_scale=shot_scale,
        )
        for b in behaviors:
            new_labels.append({
                "id": uuid.uuid4().hex[:12],
                "shot_id": shot_id,
                "layer": "l2",
                "label_type": "behavior",
                "label_value": b["behavior"],
                "source": "rule",
                "confidence": b["confidence"],
            })

    labels_path.write_text(
        json.dumps(existing_labels + new_labels, ensure_ascii=False, indent=2)
    )

    try:
        ls = json.loads(ls_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        ls = {}
    ls["l2"] = "done"
    ls_path.write_text(json.dumps(ls, indent=2))

    return mat_dir
