"""Shot boundary detection and keyframe extraction pipeline."""
from __future__ import annotations

import json
import uuid
import warnings
from pathlib import Path
from typing import NamedTuple

from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector

from services.config import anchor_root, load_config, resolve_config_path
from services.keyframes import extract_keyframe
from services.paths import ensure_material_dir, material_id, store_path


class _SimpleTimecode(NamedTuple):
    """Minimal timecode replacement for the no-cut fallback."""
    seconds: float

    def get_seconds(self) -> float:
        return self.seconds


def split_video(
    video_path: Path,
    data_root: Path | None = None,
    batch_id: str = "default",
    config_path: Path | None = None,
    mat_id: str | None = None,
) -> Path:
    """
    Detect shot boundaries, extract keyframes, write shots.json.

    Returns the material directory Path.
    """
    cfg = load_config(config_path)
    if data_root is None:
        data_root = resolve_config_path(cfg["data_root"])
    anchor = anchor_root(cfg)

    if mat_id is None:
        mat_id = material_id(video_path, anchor_root(cfg))

    mat_dir = ensure_material_dir(data_root, batch_id, mat_id)
    kf_dir = mat_dir / "keyframes"
    kf_dir.mkdir(exist_ok=True)

    # Scene detection
    threshold = float(cfg["scene_detect"]["threshold"])
    min_scene_len = int(cfg["scene_detect"]["min_scene_len"])

    video = open_video(str(video_path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=threshold, min_scene_len=min_scene_len))
    manager.detect_scenes(video)
    scene_list = manager.get_scene_list()

    # If no cuts found, treat the whole video as one shot
    if not scene_list:
        from services.ffprobe import extract_facts
        facts = extract_facts(video_path)
        duration = facts["duration"]
        scene_list = [(_SimpleTimecode(0.0), _SimpleTimecode(float(duration)))]

    shots = []
    for i, (start_tc, end_tc) in enumerate(scene_list):
        start = round(start_tc.seconds, 3)
        end = round(end_tc.seconds, 3)
        mid = round((start + end) / 2, 3)

        shot_id = uuid.uuid4().hex[:12]
        prefix = f"shot_{i:04d}"

        kf_paths: dict[str, str] = {}
        # Use end - 0.05s to avoid grabbing the first frame of the next shot
        for label, ts in [("start", start), ("mid", mid), ("end", max(0.0, end - 0.05))]:
            out = kf_dir / f"{prefix}_{label}.jpg"
            try:
                extract_keyframe(video_path, ts, out)
                kf_paths[label] = store_path(out, anchor)
            except RuntimeError as exc:
                warnings.warn(f"Keyframe extraction failed for shot {i} [{label}] at {ts}s: {exc}")
                kf_paths[label] = None  # type: ignore[assignment]

        shots.append({
            "id": shot_id,
            "material_id": mat_id,
            "start_time": start,
            "end_time": end,
            "scene_number": i,
            "key_frames": kf_paths,
            "quality_grade": None,
            "is_rejected": False,
            "layer_status": {},  # populated per-shot as tagging layers run
        })

    (mat_dir / "shots.json").write_text(
        json.dumps(shots, ensure_ascii=False, indent=2)
    )

    # Update layer_status
    ls_path = mat_dir / "layer_status.json"
    try:
        ls = json.loads(ls_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        ls = {}
    ls["split"] = "done"
    ls_path.write_text(json.dumps(ls, indent=2))

    return mat_dir
