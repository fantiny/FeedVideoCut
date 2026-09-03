"""Tests for material ingest (L0 layer)."""
from pathlib import Path
import json
import pytest

from pipelines.ingest import ingest_video

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "input" / "8月第60条信息流" / "v1" / "v1.mp4"
)


@pytest.fixture
def video():
    if not SAMPLE.exists():
        pytest.skip("sample video not found; ensure input/ is symlinked")
    return SAMPLE


def test_ingest_creates_material_json(video, tmp_path):
    mat_dir = ingest_video(video, data_root=tmp_path, batch_id="test_batch")
    material_file = mat_dir / "material.json"
    assert material_file.exists(), "material.json should be created"
    data = json.loads(material_file.read_text())
    assert data["duration"] > 0
    assert data["width"] == 1080
    assert data["height"] == 1920
    assert data["codec"] == "h264"
    assert data["has_audio"] in (True, False)
    assert data["file_name"] == "v1.mp4"
    assert "ingest_time" in data


def test_ingest_does_not_copy_video(video, tmp_path):
    mat_dir = ingest_video(video, data_root=tmp_path, batch_id="test_batch")
    mp4_files = list(mat_dir.rglob("*.mp4"))
    assert mp4_files == [], "original video must not be copied"


def test_ingest_idempotent(video, tmp_path):
    """Running ingest twice should overwrite cleanly (same material id)."""
    dir1 = ingest_video(video, data_root=tmp_path, batch_id="test_batch")
    dir2 = ingest_video(video, data_root=tmp_path, batch_id="test_batch")
    assert dir1 == dir2


def test_layer_status_written(video, tmp_path):
    mat_dir = ingest_video(video, data_root=tmp_path, batch_id="test_batch")
    status = json.loads((mat_dir / "layer_status.json").read_text())
    assert status["l0"] == "done"
