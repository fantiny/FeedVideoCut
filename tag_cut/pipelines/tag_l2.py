"""
L2 tagging: audio event detection + behavior rules from taxonomy config.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from providers.audio.vad_provider import detect_audio_events
from services.config import load_config
from services.paths import ensure_material_dir, material_id
from services.taxonomy import (
    infer_audio_role,
    infer_audio_texture,
    infer_behaviors,
    load_taxonomy,
)


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
    """Back-compat wrapper used by unit tests; delegates to taxonomy rules."""
    tax = load_taxonomy()
    audio_names = [e["event"] for e in audio_events]
    ctx = {
        "audio": audio_names,
        "duration": duration,
        "has_dog": has_dog,
        "has_person": has_person,
        "has_bowl": has_bowl,
        "closeup": shot_scale in tax.closeup_scales(),
    }
    # If no audio events at all, treat as ambient for fallback ambient rules
    if not audio_names:
        ctx["audio"] = ["ambient"]
    return infer_behaviors(tax, ctx)


def tag_l2(
    video_path: Path,
    data_root: Path | None = None,
    batch_id: str = "default",
    config_path: Path | None = None,
    mat_id: str | None = None,
) -> Path:
    cfg = load_config(config_path)
    tax = load_taxonomy()
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

        audio_names = [e["event"] for e in audio_events]
        texture, t_conf = infer_audio_texture(tax, audio_names)
        role, r_conf = infer_audio_role(tax, texture, duration)
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

        ctx = {
            "audio": audio_names or ["ambient"],
            "duration": duration,
            "has_dog": has_dog,
            "has_person": has_person,
            "has_bowl": has_bowl,
            "closeup": (shot_scale in tax.closeup_scales()) if shot_scale else False,
        }
        for b in infer_behaviors(tax, ctx):
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
