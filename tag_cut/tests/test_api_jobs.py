"""Tests for FastAPI job API."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import pytest

from fastapi.testclient import TestClient
from services.app import app

client = TestClient(app)

SAMPLE_BATCH = (
    Path(__file__).resolve().parents[2] / "input" / "8月第60条信息流"
)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_job_missing_batch():
    r = client.post("/jobs", json={"batch_path": "/nonexistent/path"})
    assert r.status_code == 404


def test_create_job_queued():
    if not SAMPLE_BATCH.exists():
        pytest.skip("sample batch not found")
    # Stub run_pipeline to avoid full processing in unit test
    with patch("pipelines.run.run_pipeline") as mock_run:
        mock_run.return_value = {"l0": "done"}
        r = client.post("/jobs", json={"batch_path": str(SAMPLE_BATCH)})
        assert r.status_code == 202
        data = r.json()
        assert "id" in data
        assert data["status"] in ("queued", "running", "done")
        assert data["batch_id"] == SAMPLE_BATCH.name
        job_id = data["id"]

    # Poll job status
    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == job_id


def test_get_job_not_found():
    r = client.get("/jobs/nonexistent_id")
    assert r.status_code == 404


def test_patch_shot_not_found():
    r = client.patch("/shots/nonexistent_shot", json={"is_rejected": True})
    assert r.status_code == 404


def test_list_materials_missing_batch():
    r = client.get("/materials/nonexistent_batch_xyz")
    assert r.status_code == 404


def test_preview_shot_not_found():
    r = client.get("/shots/nonexistent_shot/preview")
    assert r.status_code == 404


def test_export_shot_not_found():
    r = client.post("/shots/nonexistent_shot/export", json={"output_dir": "/tmp"})
    assert r.status_code == 404


def test_export_shot_writes_mp4(tmp_path, monkeypatch):
    if not SAMPLE_BATCH.exists():
        pytest.skip("sample batch not found")
    sample = SAMPLE_BATCH / "v1" / "v1.mp4"
    if not sample.exists():
        pytest.skip("sample video missing")
    mat_dir = tmp_path / "batch" / "mat1"
    mat_dir.mkdir(parents=True)
    (mat_dir / "material.json").write_text(json.dumps({
        "id": "mat1",
        "file_name": "v1.mp4",
        "file_path": str(sample),
    }))
    (mat_dir / "shots.json").write_text(json.dumps([
        {"id": "cliptest01", "start_time": 0.0, "end_time": 0.4, "scene_number": 0},
    ]))
    monkeypatch.setattr("services.app.DATA_ROOT", tmp_path)
    out = tmp_path / "saved"
    r = client.post("/shots/cliptest01/export", json={"output_dir": str(out)})
    assert r.status_code == 200, r.text
    body = r.json()
    exported = Path(body["path"])
    assert exported.exists()
    assert exported.parent == out.resolve()
    assert exported.stat().st_size > 1000


def test_list_batches_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr("services.app.DATA_ROOT", tmp_path)
    a = tmp_path / "batch_a" / "mat1"
    a.mkdir(parents=True)
    (a / "material.json").write_text(json.dumps({"id": "m1", "file_name": "a.mp4"}))
    (a / "shots.json").write_text(json.dumps([{"id": "s1"}]))
    (tmp_path / "batch_a" / "batch_meta.json").write_text(json.dumps({
        "batch_id": "batch_a", "source_path": "/input/a",
    }))
    b = tmp_path / "batch_b" / "mat1"
    b.mkdir(parents=True)
    (b / "material.json").write_text(json.dumps({"id": "m2", "file_name": "b.mp4"}))

    r = client.get("/batches")
    assert r.status_code == 200
    ids = {x["batch_id"] for x in r.json()["batches"]}
    assert ids == {"batch_a", "batch_b"}

    d = client.delete("/batches/batch_a")
    assert d.status_code == 200
    assert d.json()["status"] == "deleted"
    assert not (tmp_path / "batch_a").exists()
    assert (tmp_path / "batch_b").exists()

    # other batch untouched
    r2 = client.get("/batches")
    assert {x["batch_id"] for x in r2.json()["batches"]} == {"batch_b"}


def test_delete_batch_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("services.app.DATA_ROOT", tmp_path)
    r = client.delete("/batches/../etc")
    assert r.status_code in (400, 404)

    r = client.get("/batches/lookup", params={"path": "/nonexistent/path"})
    assert r.status_code == 404


def test_lookup_batch_reports_cache(tmp_path, monkeypatch):
    if not SAMPLE_BATCH.exists():
        pytest.skip("sample batch not found")
    monkeypatch.setattr("services.app.DATA_ROOT", tmp_path)
    batch_id = SAMPLE_BATCH.name
    mat_dir = tmp_path / batch_id / "mat1"
    mat_dir.mkdir(parents=True)
    (mat_dir / "material.json").write_text(json.dumps({
        "id": "mat1", "file_name": "v1.mp4", "file_path": "/x/v1.mp4",
    }))
    (mat_dir / "shots.json").write_text(json.dumps([
        {"id": "s1", "start_time": 0, "end_time": 1},
        {"id": "s2", "start_time": 1, "end_time": 2},
    ]))
    r = client.get("/batches/lookup", params={"path": str(SAMPLE_BATCH)})
    assert r.status_code == 200
    body = r.json()
    assert body["exists"] is True
    assert body["batch_id"] == batch_id
    assert body["material_count"] == 1
    assert body["shot_count"] == 2


def test_force_job_clears_cache(tmp_path, monkeypatch):
    if not SAMPLE_BATCH.exists():
        pytest.skip("sample batch not found")
    monkeypatch.setattr("services.app.DATA_ROOT", tmp_path)
    batch_id = SAMPLE_BATCH.name
    stale = tmp_path / batch_id / "old"
    stale.mkdir(parents=True)
    (stale / "material.json").write_text("{}")
    with patch("pipelines.run.run_pipeline") as mock_run:
        mock_run.return_value = {"l0": "done"}
        r = client.post("/jobs", json={"batch_path": str(SAMPLE_BATCH), "force": True})
        assert r.status_code == 202
    assert not stale.exists()


def test_create_job_accepts_relative_batch_name():
    if not SAMPLE_BATCH.exists():
        pytest.skip("sample batch not found")
    with patch("pipelines.run.run_pipeline") as mock_run:
        mock_run.return_value = {"l0": "done"}
        r = client.post("/jobs", json={"batch_path": "../input/8月第60条信息流"})
        if r.status_code == 404:
            r = client.post("/jobs", json={"batch_path": "8月第60条信息流"})
        assert r.status_code == 202
        assert r.json()["id"]


def test_list_yolo_models_api():
    r = client.get("/models/yolo")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data and "environment" in data
    assert any(m["id"] == "yolov8n" for m in data["models"])


def test_yolo_env_probe_api():
    r = client.get("/models/yolo/env")
    assert r.status_code == 200
    assert "recommended_id" in r.json()


def test_yolo_download_unknown_model():
    r = client.post("/models/yolo/not-a-model/download", json={"force": False})
    assert r.status_code == 404


def test_search_api_empty_ok():
    r = client.get("/tags/query", params={"q": "unlikely_tag_xyz_999"})
    assert r.status_code == 200
    assert r.json()["count"] == 0
    # legacy alias
    r2 = client.get("/search", params={"q": "unlikely_tag_xyz_999"})
    assert r2.status_code == 200


def test_search_facets_api():
    r = client.get("/tags/facets")
    assert r.status_code == 200
    assert "label_types" in r.json()


def test_health_reports_features():
    r = client.get("/health")
    assert r.status_code == 200
    assert "search" in r.json().get("features", [])
