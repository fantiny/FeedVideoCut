"""Tests for scene split and keyframe extraction."""
from pathlib import Path
import json
import pytest

from pipelines.split import split_video

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "input" / "8月第60条信息流" / "v1" / "v1.mp4"
)


@pytest.fixture
def video():
    if not SAMPLE.exists():
        pytest.skip("sample video not found")
    return SAMPLE


def test_split_creates_shots_json(video, tmp_path):
    mat_dir = split_video(video, data_root=tmp_path, batch_id="test_batch")
    shots_file = mat_dir / "shots.json"
    assert shots_file.exists()
    shots = json.loads(shots_file.read_text())
    assert isinstance(shots, list)
    assert len(shots) >= 1


def test_shots_have_required_fields(video, tmp_path):
    mat_dir = split_video(video, data_root=tmp_path, batch_id="test_batch")
    shots = json.loads((mat_dir / "shots.json").read_text())
    for shot in shots:
        assert "id" in shot
        assert "start_time" in shot
        assert "end_time" in shot
        assert shot["end_time"] > shot["start_time"]
        assert "scene_number" in shot
        assert "key_frames" in shot
        assert "is_rejected" in shot


def test_keyframes_extracted(video, tmp_path):
    mat_dir = split_video(video, data_root=tmp_path, batch_id="test_batch")
    shots = json.loads((mat_dir / "shots.json").read_text())
    kf_dir = mat_dir / "keyframes"
    assert kf_dir.exists()
    # At least the first shot should have a start keyframe
    first = shots[0]
    if first["key_frames"].get("start"):
        assert Path(first["key_frames"]["start"]).exists()


def test_layer_status_updated(video, tmp_path):
    mat_dir = split_video(video, data_root=tmp_path, batch_id="test_batch")
    status = json.loads((mat_dir / "layer_status.json").read_text())
    assert status.get("split") == "done"
