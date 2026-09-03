"""
L2 tagging: audio event detection + behavior rule recognition.

Behavior rules (对齐 V03 素材库 SOP — 从 bbox 时序 + 音频事件推断):
  凑近闻  (approaching)  : shot duration < 1.5s, low ZCR audio or silent
  第一口  (first_bite)   : detected chew event, short shot
  大口进食 (eating)       : chew event, longer shot
  舔碗    (lick_bowl)    : lick / chew event, very short shot
  摇尾    (wag_tail)     : bark or ambient, no speech (heuristic only)
  等待投喂 (waiting)      : silent / ambient, shot > 2s
  人物讲解 (commentary)   : speech event

If audio is disabled in config, audio step is skipped and behaviors are
inferred from shot duration alone (lower confidence).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from providers.audio.vad_provider import detect_audio_events
from services.config import load_config
from services.paths import ensure_material_dir, material_id


def _infer_behaviors(audio_events: list[dict], duration: float) -> list[dict]:
    """
    Map audio events + duration to V03 behavior labels.
    Returns list of behavior dicts with confidence.
    """
    event_names = {e["event"] for e in audio_events}
    behaviors: list[dict] = []

    if "speech" in event_names:
        behaviors.append({"behavior": "人物讲解", "confidence": 0.75})

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
        if "silent" in event_names or "ambient" in event_names:
            if duration > 2.0:
                behaviors.append({"behavior": "等待投喂", "confidence": 0.4})
            else:
                behaviors.append({"behavior": "凑近闻", "confidence": 0.4})

    return behaviors


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

        # --- Audio events ---
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

        # --- Behavior inference ---
        behaviors = _infer_behaviors(audio_events, duration)
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
