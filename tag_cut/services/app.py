"""
FastAPI application for tag_cut pipeline.

Endpoints:
  GET  /health
  GET  /batches                       — list analyzed batches under data_root
  GET  /batches/lookup                — resolve input path + cache status
  DELETE /batches/{batch_id}          — delete one batch's analysis data
  POST /jobs                          — submit batch job
  GET  /jobs/{job_id}                 — job status
  GET  /materials/{batch_id}          — list materials in batch
  GET  /materials/{batch_id}/{mat_id} — material detail + shots + labels
  PATCH /shots/{shot_id}             — human edit (reject / label override)
  GET  /shots/{shot_id}/preview      — playable mp4 for one clip
  POST /shots/{shot_id}/export       — save clip mp4 to a directory
  POST /exports/{batch_id}            — trigger index export
  GET  /models/yolo                   — YOLO catalog + local status + env badges
  GET  /models/yolo/env               — re-probe machine, support/recommend
  POST /models/yolo/{id}/download     — download weights to models/
  GET  /models/yolo/{id}/download     — download progress
  POST /models/yolo/activate          — set active weights (config/local.yaml)
  GET  /taxonomy                      — dimension registry + enum values
  POST /taxonomy/reload               — clear taxonomy cache after config edit
  GET  /search                        — tag search across materials/shots
  GET  /search/facets                 — label type/value hints for UI
"""
from __future__ import annotations

import json
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from services.config import anchor_root, load_config, resolve_config_path
from services.jobs import job_store
from services.paths import (
    public_data_url,
    resolve_batch_path,
    resolve_media_path,
    store_path,
)

app = FastAPI(title="tag_cut API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Electron renderer on localhost
    allow_methods=["*"],
    allow_headers=["*"],
)

cfg = load_config()
DATA_ROOT = resolve_config_path(cfg["data_root"])
DATA_ROOT.mkdir(parents=True, exist_ok=True)
INPUT_ROOT = resolve_config_path(cfg["input_root"])
ANCHOR = anchor_root(cfg)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class CreateJobRequest(BaseModel):
    batch_path: str
    video_glob: str = "**/*.mp4"
    layers: list[str] | None = None
    force: bool = False  # True = wipe previous data_root/<batch_id> then regenerate
    # Optional custom subdirectory name under data_root (defaults to input folder name)
    batch_id: str | None = None


class ShotPatchRequest(BaseModel):
    is_rejected: bool | None = None
    label_overrides: list[dict] | None = None  # list of label dicts with source="human"


class ShotExportRequest(BaseModel):
    output_dir: str
    filename: str | None = None


def _safe_batch_id(raw: str) -> str:
    """Sanitize a batch_id so it is a single path segment under data_root."""
    name = Path(raw).name.strip()
    name = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", name, flags=re.UNICODE).strip("._")
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="invalid batch_id")
    return name


def _batch_dir(batch_id: str) -> Path:
    """Return data_root/<batch_id>, rejecting path traversal."""
    safe = _safe_batch_id(batch_id)
    dest = (DATA_ROOT / safe).resolve()
    if dest != DATA_ROOT and DATA_ROOT not in dest.parents:
        raise HTTPException(status_code=400, detail="batch_id escapes data_root")
    if dest == DATA_ROOT:
        raise HTTPException(status_code=400, detail="invalid batch_id")
    return dest


def _write_batch_meta(batch_id: str, source_path: str) -> None:
    dest = _batch_dir(batch_id)
    dest.mkdir(parents=True, exist_ok=True)
    meta_path = dest / "batch_meta.json"
    prev: dict = {}
    if meta_path.exists():
        try:
            prev = json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            prev = {}
    source = store_path(Path(source_path), ANCHOR)
    meta = {
        **prev,
        "batch_id": batch_id,
        "source_path": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if "created_at" not in meta:
        meta["created_at"] = meta["updated_at"]
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------

def _run_job(
    job_id: str,
    batch_path: str,
    video_glob: str,
    layers: list[str] | None,
    batch_id: str,
):
    from pipelines.run import run_pipeline

    batch = Path(batch_path)
    videos = sorted(
        batch.rglob("*.mp4") if video_glob == "**/*.mp4" else batch.glob(video_glob)
    )
    job_store.set_videos(job_id, [str(v) for v in videos])
    job_store.update_status(job_id, "running")
    _write_batch_meta(batch_id, str(batch))

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
    return {
        "status": "ok",
        "features": ["search", "yolo_models", "clips", "batches", "taxonomy"],
    }


def _batch_cache_summary(batch_id: str) -> dict:
    """Summarize existing analysis under data_root/<batch_id>."""
    batch_dir = DATA_ROOT / batch_id
    materials: list[dict] = []
    shot_count = 0
    source_path = ""
    updated_at = ""
    if batch_dir.exists():
        meta_path = batch_dir / "batch_meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                source_path = str(meta.get("source_path") or "")
                updated_at = str(meta.get("updated_at") or meta.get("created_at") or "")
            except json.JSONDecodeError:
                pass
        for mat_dir in sorted(batch_dir.iterdir()):
            if not mat_dir.is_dir():
                continue
            mf = mat_dir / "material.json"
            if not mf.exists():
                continue
            material = json.loads(mf.read_text())
            materials.append(material)
            if not source_path:
                source_path = str(
                    resolve_media_path(material.get("file_path"), ANCHOR) or ""
                )
            shots_path = mat_dir / "shots.json"
            if shots_path.exists():
                try:
                    shot_count += len(json.loads(shots_path.read_text()))
                except json.JSONDecodeError:
                    pass
    return {
        "batch_id": batch_id,
        "exists": len(materials) > 0,
        "material_count": len(materials),
        "shot_count": shot_count,
        "materials": materials,
        "data_dir": str(batch_dir),
        "source_path": source_path,
        "updated_at": updated_at,
    }


@app.get("/batches")
def list_batches():
    """List all analyzed batches stored as subdirs under data_root."""
    items: list[dict] = []
    if not DATA_ROOT.exists():
        return {"batches": items}
    for child in sorted(DATA_ROOT.iterdir()):
        if not child.is_dir():
            continue
        summary = _batch_cache_summary(child.name)
        if summary["exists"]:
            # drop heavy materials payload for list view
            items.append({k: v for k, v in summary.items() if k != "materials"})
    return {"batches": items}


@app.delete("/batches/{batch_id}")
def delete_batch(batch_id: str):
    """Delete one batch analysis directory under data_root. Does not touch input/."""
    dest = _batch_dir(batch_id)
    if not dest.exists():
        raise HTTPException(status_code=404, detail=f"batch {batch_id!r} not found")
    shutil.rmtree(dest)
    return {"status": "deleted", "batch_id": batch_id}


@app.get("/batches/lookup")
def lookup_batch(path: str, batch_id: str | None = None):
    """
    Resolve a batch directory and report whether prior analysis results exist.
    Does not start a job.
    """
    batch = resolve_batch_path(path, cwd=Path.cwd(), input_root=INPUT_ROOT)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"batch_path not found: {path}")
    bid = _safe_batch_id(batch_id) if batch_id else batch.name
    summary = _batch_cache_summary(bid)
    return {
        "batch_path": str(batch),
        "input_exists": True,
        **summary,
    }


@app.post("/jobs", status_code=202)
def create_job(req: CreateJobRequest):
    batch = resolve_batch_path(
        req.batch_path, cwd=Path.cwd(), input_root=INPUT_ROOT
    )
    if batch is None:
        raise HTTPException(status_code=404, detail=f"batch_path not found: {req.batch_path}")

    batch_id = _safe_batch_id(req.batch_id) if req.batch_id else batch.name
    dest = _batch_dir(batch_id)

    if req.force and dest.exists():
        shutil.rmtree(dest)

    job = job_store.create(str(batch), req.video_glob)
    # expose chosen batch_id on the job response via batch_path name override in to_dict —
    # patch created job fields by writing meta early and returning enriched dict
    t = threading.Thread(
        target=_run_job,
        args=(job.id, str(batch), req.video_glob, req.layers, batch_id),
        daemon=True,
    )
    t.start()
    payload = job.to_dict()
    payload["batch_id"] = batch_id
    payload["batch_path"] = str(batch)
    return payload


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
    for shot in result.get("shots") or []:
        frames = shot.get("key_frames") or {}
        shot["key_frames"] = {
            k: public_data_url(str(resolve_media_path(v, ANCHOR)), DATA_ROOT) or v
            for k, v in frames.items()
        }
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


@app.get("/shots/{shot_id}/preview")
def preview_shot(shot_id: str):
    """Return a cached mp4 of this shot for in-app playback."""
    from fastapi.responses import FileResponse
    from services.clips import ClipError, extract_clip, find_shot

    try:
        mat_dir, shot, material = find_shot(DATA_ROOT, shot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    src = resolve_media_path(material.get("file_path"), ANCHOR) or Path("")
    cache = mat_dir / "clip_previews" / f"{shot_id}.mp4"
    if not cache.exists() or cache.stat().st_size == 0:
        try:
            extract_clip(src, float(shot["start_time"]), float(shot["end_time"]), cache)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ClipError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(path=str(cache), media_type="video/mp4", filename=f"{shot_id}.mp4")


@app.post("/shots/{shot_id}/export")
def export_shot(shot_id: str, req: ShotExportRequest):
    """Cut this shot and save an mp4 into output_dir (does not modify originals)."""
    from services.clips import ClipError, default_clip_filename, extract_clip, find_shot

    try:
        _mat_dir, shot, material = find_shot(DATA_ROOT, shot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    src = resolve_media_path(material.get("file_path"), ANCHOR) or Path("")
    out_dir = Path(req.output_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = (Path.cwd() / out_dir).resolve()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"cannot create output_dir: {exc}") from exc

    filename = req.filename or default_clip_filename(material, shot)
    dest = (out_dir / Path(filename).name).resolve()
    try:
        extract_clip(src, float(shot["start_time"]), float(shot["end_time"]), dest)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ClipError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "exported", "path": str(dest), "filename": dest.name}


@app.post("/exports/{batch_id}", status_code=202)
def trigger_export(batch_id: str):
    """Trigger synchronous index export for a batch."""
    from pipelines.export_index import export_batch
    batch_dir = DATA_ROOT / batch_id
    if not batch_dir.exists():
        raise HTTPException(status_code=404, detail=f"batch {batch_id!r} not found")
    out = export_batch(batch_id=batch_id, data_root=DATA_ROOT)
    return {"status": "exported", "index_json": str(out / "index.json"), "index_csv": str(out / "index.csv")}


# ---------------------------------------------------------------------------
# YOLO models
# ---------------------------------------------------------------------------

class ModelDownloadRequest(BaseModel):
    force: bool = False


class ModelActivateRequest(BaseModel):
    model_id: str


@app.get("/models/yolo")
def list_yolo_models():
    from services.yolo_models import list_models_with_status
    return list_models_with_status()


@app.get("/models/yolo/env")
def yolo_env_probe():
    """Re-probe local environment and return support/recommend badges."""
    from services.yolo_models import list_models_with_status, probe_environment
    env = probe_environment()
    listing = list_models_with_status()
    return {"environment": env, "recommended_id": listing["recommended_id"], "models": listing["models"]}


@app.post("/models/yolo/{model_id}/download", status_code=202)
def download_yolo_model(model_id: str, req: ModelDownloadRequest | None = None):
    from services.yolo_models import catalog_by_id, download_model, download_status

    if not catalog_by_id(model_id):
        raise HTTPException(status_code=404, detail=f"unknown model: {model_id}")
    force = bool(req.force) if req else False
    st = download_status(model_id)
    if st.get("status") == "downloading":
        return {"status": "downloading", "model_id": model_id, **st}

    def _worker():
        try:
            download_model(model_id, force=force)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_worker, daemon=True).start()
    return {"status": "started", "model_id": model_id}


@app.get("/models/yolo/{model_id}/download")
def get_yolo_download_status(model_id: str):
    from services.yolo_models import catalog_by_id, download_status, models_dir
    if not catalog_by_id(model_id):
        raise HTTPException(status_code=404, detail=f"unknown model: {model_id}")
    st = download_status(model_id)
    spec = catalog_by_id(model_id)
    path = models_dir() / spec.filename  # type: ignore[union-attr]
    if path.exists() and st.get("status") in (None, "idle"):
        st = {"status": "done", "path": str(path), "bytes": path.stat().st_size}
    return {"model_id": model_id, **st}


@app.post("/models/yolo/activate")
def activate_yolo_model(req: ModelActivateRequest):
    from services.yolo_models import set_active_model
    try:
        return {"status": "ok", **set_active_model(req.model_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Taxonomy (configurable tag dimensions)
# ---------------------------------------------------------------------------

@app.get("/taxonomy")
def get_taxonomy():
    """Return dimension registry + enum values for UI / agents."""
    from services.taxonomy import load_taxonomy
    return load_taxonomy().public_dict()


@app.post("/taxonomy/reload")
def reload_taxonomy():
    """Clear taxonomy cache after editing taxonomy.yaml / taxonomy.local.yaml."""
    from services.taxonomy import clear_taxonomy_cache, load_taxonomy
    clear_taxonomy_cache()
    return {"status": "ok", "version": load_taxonomy().version}


# ---------------------------------------------------------------------------
# Tag search
# ---------------------------------------------------------------------------

@app.get("/tags/query")
@app.get("/search")  # alias; prefer /tags/query (some clients block paths named /search)
def search(
    q: str = "",
    batch_id: str | None = None,
    label_type: str | None = None,
    layer: str | None = None,
    limit: int = 100,
):
    from services.search import search_labels
    return search_labels(
        DATA_ROOT,
        q,
        batch_id=batch_id,
        label_type=label_type or None,
        layer=layer or None,
        limit=limit,
    )


@app.get("/tags/facets")
@app.get("/search/facets")
def search_facets(batch_id: str | None = None):
    from services.search import list_label_facets
    return list_label_facets(DATA_ROOT, batch_id=batch_id)


app.mount("/files", StaticFiles(directory=str(DATA_ROOT)), name="files")
