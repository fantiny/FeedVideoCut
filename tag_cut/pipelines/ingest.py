"""Ingest a single video file: extract L0 facts and write material.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from services.config import anchor_root, load_config, resolve_config_path
from services.ffprobe import extract_facts
from services.paths import material_id, material_dir, store_path


def ingest_video(
    video_path: Path,
    data_root: Path | None = None,
    batch_id: str = "default",
    config_path: Path | None = None,
) -> Path:
    """
    Ingest one video.

    Returns the material directory Path containing material.json.
    Does NOT copy or modify the video file.
    """
    cfg = load_config(config_path)
    if data_root is None:
        data_root = resolve_config_path(cfg["data_root"])
    anchor = anchor_root(cfg)

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    mat_id = material_id(video_path, anchor_root(cfg))
    mat_dir = material_dir(data_root, batch_id, mat_id)

    facts = extract_facts(video_path)

    material = {
        "id": mat_id,
        "file_name": video_path.name,
        "file_path": store_path(video_path, anchor),
        "ingest_time": datetime.now(timezone.utc).isoformat(),
        **facts,
    }

    (mat_dir / "material.json").write_text(
        json.dumps(material, ensure_ascii=False, indent=2)
    )
    # initialise layer_status file
    (mat_dir / "layer_status.json").write_text(
        json.dumps({"l0": "done"}, indent=2)
    )
    return mat_dir
