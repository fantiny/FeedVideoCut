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
    with patch("services.app.run_pipeline") as mock_run:
        mock_run.return_value = {"l0": "done"}
        r = client.post("/jobs", json={"batch_path": str(SAMPLE_BATCH)})
        assert r.status_code == 202
        data = r.json()
        assert "id" in data
        assert data["status"] in ("queued", "running", "done")
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
