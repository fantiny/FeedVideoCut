"""
FastAPI application for tag_cut pipeline.

Endpoints:
  GET  /health
  POST /jobs                          — submit batch job
  GET  /jobs/{job_id}                 — job status
  GET  /materials/{batch_id}          — list materials in batch
  GET  /materials/{batch_id}/{mat_id} — material detail + shots + labels
  PATCH /shots/{shot_id}             — human edit (reject / label override)
  POST /exports/{batch_id}            — trigger export
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.config import load_config
from services.jobs import job_store
from pipelines.run import run_pipeline

app = FastAPI(title="tag_cut API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Electron renderer on localhost
    allow_methods=["*"],
    allow_headers=["*"],
)

cfg = load_config()
DATA_ROOT = Path(cfg["data_root"]).resolve()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class CreateJobRequest(BaseModel):
    batch_path: str
    video_glob: str = "**/*.mp4"
    layers: list[str] | None = None


class ShotPatchRequest(BaseModel):
    is_rejected: bool | None = None
    label_overrides: list[dict] | None = None  # list of label dicts with source="human"


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------

def _run_job(job_id: str, batch_path: str, video_glob: str, layers: list[str] | None):
    batch = Path(batch_path)
    videos = sorted(batch.rglob("*.mp4") if video_glob == "**/*.mp4" else batch.glob(video_glob))
    job_store.set_videos(job_id, [str(v) for v in videos])
    job_store.update_status(job_id, "running")

    batch_id = batch.name

    try:
        for video in videos:
            def cb(layer, status, error, _v=str(video)):
                job_store.add_progress(job_id, f"{_v}:{layer}", status, error)

            run_pipeline(
                video_path=video,
                batch_id=batch_id,
                data_root=DATA_ROOT,
                layers=layers,
                progress_callback=cb,
            )
        job_store.update_status(job_id, "done")
    except Exception as exc:  # noqa: BLE001
        job_store.update_status(job_id, "failed", str(exc))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs", status_code=202)
def create_job(req: CreateJobRequest):
    batch = Path(req.batch_path)
    if not batch.exists():
        raise HTTPException(status_code=404, detail=f"batch_path not found: {batch}")
    job = job_store.create(req.batch_path, req.video_glob)
    t = threading.Thread(
        target=_run_job,
        args=(job.id, req.batch_path, req.video_glob, req.layers),
        daemon=True,
    )
    t.start()
    return job.to_dict()


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job.to_dict()


@app.get("/materials/{batch_id}")
def list_materials(batch_id: str):
    batch_dir = DATA_ROOT / batch_id
    if not batch_dir.exists():
        raise HTTPException(status_code=404, detail=f"batch {batch_id!r} not found in data_root")
    materials = []
    for mat_dir in sorted(batch_dir.iterdir()):
        mf = mat_dir / "material.json"
        if mf.exists():
            materials.append(json.loads(mf.read_text()))
    return materials


@app.get("/materials/{batch_id}/{mat_id}")
def get_material(batch_id: str, mat_id: str):
    mat_dir = DATA_ROOT / batch_id / mat_id
    if not mat_dir.exists():
        raise HTTPException(status_code=404, detail="material not found")
    result: dict = {}
    for fname in ("material.json", "shots.json", "labels.json", "scores.json", "layer_status.json"):
        p = mat_dir / fname
        if p.exists():
            result[fname.replace(".json", "")] = json.loads(p.read_text())
    return result


@app.patch("/shots/{shot_id}")
def patch_shot(shot_id: str, req: ShotPatchRequest):
    """
    Update a shot's is_rejected flag and/or append human label overrides.
    Searches all batch dirs for the shot.
    """
    # Find which material contains this shot
    updated = False
    for batch_dir in DATA_ROOT.iterdir():
        if not batch_dir.is_dir():
            continue
        for mat_dir in batch_dir.iterdir():
            shots_path = mat_dir / "shots.json"
            labels_path = mat_dir / "labels.json"
            if not shots_path.exists():
                continue
            shots = json.loads(shots_path.read_text())
            shot = next((s for s in shots if s["id"] == shot_id), None)
            if shot is None:
                continue

            # Update rejection flag
            if req.is_rejected is not None:
                shot["is_rejected"] = req.is_rejected
                shots_path.write_text(json.dumps(shots, ensure_ascii=False, indent=2))

            # Append human labels
            if req.label_overrides:
                existing = json.loads(labels_path.read_text()) if labels_path.exists() else []
                for lb in req.label_overrides:
                    lb["shot_id"] = shot_id
                    lb["source"] = "human"
                labels_path.write_text(
                    json.dumps(existing + req.label_overrides, ensure_ascii=False, indent=2)
                )
            updated = True
            return {"status": "updated", "shot_id": shot_id}

    if not updated:
        raise HTTPException(status_code=404, detail=f"shot {shot_id!r} not found")


@app.post("/exports/{batch_id}", status_code=202)
def trigger_export(batch_id: str):
    """Trigger synchronous index export for a batch."""
    from pipelines.export_index import export_batch
    batch_dir = DATA_ROOT / batch_id
    if not batch_dir.exists():
        raise HTTPException(status_code=404, detail=f"batch {batch_id!r} not found")
    out = export_batch(batch_id=batch_id, data_root=DATA_ROOT)
    return {"status": "exported", "index_json": str(out / "index.json"), "index_csv": str(out / "index.csv")}
