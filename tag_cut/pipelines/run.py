"""
Pipeline orchestrator: runs L0 → split → L1 → L2 → L3_L6 for one video.

Each layer writes its own layer_status.json entry so individual layers
can be re-run without re-processing everything.
"""
from __future__ import annotations

import json
import traceback
from pathlib import Path

from pipelines.ingest import ingest_video
from pipelines.split import split_video
from pipelines.tag_l1 import tag_l1
from pipelines.tag_l2 import tag_l2
from pipelines.tag_l3_l6 import tag_l3_l6
from services.config import load_config
from services.paths import material_id, ensure_material_dir

# Layer execution order (matches config pipeline.layers)
LAYER_ORDER = ["l0", "split", "l1", "l2", "l3_l6"]


def run_pipeline(
    video_path: Path,
    batch_id: str = "default",
    data_root: Path | None = None,
    config_path: Path | None = None,
    layers: list[str] | None = None,
    progress_callback=None,
) -> dict:
    """
    Run the full (or partial) pipeline for one video.

    progress_callback(stage: str, status: str, error: str | None) is called
    after each stage. status is "done" or "failed".

    Returns final layer_status dict.
    """
    cfg = load_config(config_path)
    if data_root is None:
        data_root = Path(cfg["data_root"])

    layers_to_run = layers or LAYER_ORDER
    mat_id = material_id(video_path)
    mat_dir = ensure_material_dir(data_root, batch_id, mat_id)
    ls_path = mat_dir / "layer_status.json"

    def _status() -> dict:
        try:
            return json.loads(ls_path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _notify(stage: str, status: str, error: str | None = None):
        if progress_callback:
            progress_callback(stage, status, error)

    kwargs = dict(
        video_path=video_path,
        data_root=data_root,
        batch_id=batch_id,
        config_path=config_path,
        mat_id=mat_id,
    )

    stage_fns = {
        "l0": lambda: ingest_video(**{k: v for k, v in kwargs.items() if k != "mat_id"}),
        "split": lambda: split_video(**kwargs),
        "l1": lambda: tag_l1(**kwargs),
        "l2": lambda: tag_l2(**kwargs),
        "l3_l6": lambda: tag_l3_l6(**kwargs),
    }

    for layer in layers_to_run:
        fn = stage_fns.get(layer)
        if fn is None:
            continue
        try:
            fn()
            _notify(layer, "done")
        except Exception as exc:  # noqa: BLE001
            err = traceback.format_exc()
            # Write failure into layer_status
            ls = _status()
            ls[layer] = f"failed: {exc}"
            ls_path.write_text(json.dumps(ls, indent=2))
            _notify(layer, "failed", str(exc))
            # Continue to next layer (don't abort entire pipeline)

    return _status()
