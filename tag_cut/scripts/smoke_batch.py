#!/usr/bin/env python3
"""
Smoke test: run the full pipeline on a batch (or a single video) and print a summary.

Usage:
  cd tag_cut
  PYTHONPATH=. python scripts/smoke_batch.py --batch "../input/8月第60条信息流" --limit 1
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import sys

# Ensure the tag_cut package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.run import run_pipeline
from services.config import load_config
from services.paths import material_id, ensure_material_dir


def run_smoke(batch_path: Path, limit: int | None, config_path: Path | None):
    cfg = load_config(config_path)
    data_root = (Path(__file__).parents[1] / cfg["data_root"]).resolve()
    exports_root = (Path(__file__).parents[1] / cfg["exports_root"]).resolve()

    videos = sorted(batch_path.rglob("*.mp4"))
    if limit:
        videos = videos[:limit]

    if not videos:
        print(f"[smoke] No .mp4 files found in {batch_path}", file=sys.stderr)
        sys.exit(1)

    batch_id = batch_path.name
    print(f"[smoke] Batch: {batch_id}  |  Videos: {len(videos)}  |  data_root: {data_root}")

    for video in videos:
        print(f"\n{'─'*60}")
        print(f"[smoke] Processing: {video.name}")
        t0 = time.perf_counter()

        def cb(layer, status, error=None):
            mark = "✓" if status == "done" else "✗"
            msg = f"  {mark} {layer}: {status}"
            if error:
                msg += f"  [{error[:80]}]"
            print(msg)

        final_status = run_pipeline(
            video_path=video,
            batch_id=batch_id,
            data_root=data_root,
            config_path=config_path,
            progress_callback=cb,
        )

        elapsed = time.perf_counter() - t0
        mat_id = material_id(video)
        mat_dir = ensure_material_dir(data_root, batch_id, mat_id)

        # Summary
        shots_file = mat_dir / "shots.json"
        labels_file = mat_dir / "labels.json"
        scores_file = mat_dir / "scores.json"

        n_shots = len(json.loads(shots_file.read_text())) if shots_file.exists() else 0
        n_labels = len(json.loads(labels_file.read_text())) if labels_file.exists() else 0
        n_scores = len(json.loads(scores_file.read_text())) if scores_file.exists() else 0
        n_keyframes = len(list((mat_dir / "keyframes").glob("*.jpg"))) if (mat_dir / "keyframes").exists() else 0

        print(f"\n  shots={n_shots}  keyframes={n_keyframes}  labels={n_labels}  scores={n_scores}")
        print(f"  layer_status: {final_status}")
        print(f"  elapsed: {elapsed:.1f}s")

    # Export
    print(f"\n{'─'*60}")
    print(f"[smoke] Exporting index…")
    from pipelines.export_index import export_batch
    out = export_batch(batch_id=batch_id, data_root=data_root, exports_root=exports_root)
    rows_file = out / "index.json"
    n_rows = len(json.loads(rows_file.read_text())) if rows_file.exists() else 0
    print(f"  ✓ index.json: {n_rows} rows → {out}")
    print(f"  ✓ index.csv  → {out / 'index.csv'}")
    print("\n[smoke] Done ✓")


def main():
    p = argparse.ArgumentParser(description="tag_cut smoke test")
    p.add_argument("--batch", required=True, help="Path to batch directory (contains v1/, v2/, …)")
    p.add_argument("--limit", type=int, default=None, help="Max videos to process")
    p.add_argument("--config", default=None, help="Path to config override YAML")
    args = p.parse_args()

    batch = Path(args.batch).resolve()
    if not batch.exists():
        print(f"[smoke] ERROR: batch path does not exist: {batch}", file=sys.stderr)
        sys.exit(1)

    config_path = Path(args.config).resolve() if args.config else None
    run_smoke(batch, args.limit, config_path)


if __name__ == "__main__":
    main()
