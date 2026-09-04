"""Tests for L1 vision tagging."""
from pathlib import Path
import json
import pytest

from providers.vision.shot_scale import estimate_shot_scale
from providers.vision.quality import estimate_quality_grade

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "input" / "8月第60条信息流" / "v1" / "v1.mp4"
)

# ---------------------------------------------------------------------------
# Unit tests — no video required
# ---------------------------------------------------------------------------

def test_shot_scale_extreme_close_up():
    dets = [{"bbox_norm": [0.1, 0.1, 0.9, 0.9], "confidence": 0.9,
             "class_name": "dog", "bbox": [0, 0, 100, 100]}]
    scale, conf = estimate_shot_scale(dets)
    assert scale == "大特写"
    assert conf == 0.9


def test_shot_scale_wide():
    dets = [{"bbox_norm": [0.4, 0.45, 0.6, 0.50], "confidence": 0.8,
             "class_name": "dog", "bbox": [0, 0, 10, 10]}]
    scale, conf = estimate_shot_scale(dets)
    assert scale == "全景"


def test_shot_scale_no_detections():
    scale, conf = estimate_shot_scale([])
    assert scale == "未知"
    assert conf == 0.0


def test_quality_grade_missing_image(tmp_path):
    grade, score = estimate_quality_grade(tmp_path / "no_file.jpg")
    assert grade == "?"

# ---------------------------------------------------------------------------
# Integration tests — require sample video
# ---------------------------------------------------------------------------

@pytest.fixture
def prepared_mat_dir(tmp_path):
    if not SAMPLE.exists():
        pytest.skip("sample video not found; ensure input/ is symlinked")
    from pipelines.ingest import ingest_video
    from pipelines.split import split_video
    ingest_video(SAMPLE, data_root=tmp_path, batch_id="test")
    return split_video(SAMPLE, data_root=tmp_path, batch_id="test")


def test_tag_l1_creates_labels(prepared_mat_dir, tmp_path):
    from pipelines.tag_l1 import tag_l1
    tag_l1(SAMPLE, data_root=tmp_path, batch_id="test")
    labels = json.loads((prepared_mat_dir / "labels.json").read_text())
    assert isinstance(labels, list) and len(labels) > 0


def test_tag_l1_label_fields(prepared_mat_dir, tmp_path):
    from pipelines.tag_l1 import tag_l1
    tag_l1(SAMPLE, data_root=tmp_path, batch_id="test")
    labels = json.loads((prepared_mat_dir / "labels.json").read_text())
    for label in labels:
        for key in ["id", "shot_id", "layer", "label_type", "label_value", "source", "confidence"]:
            assert key in label, f"Missing key {key!r} in label"
        assert label["layer"] == "l1"


def test_tag_l1_layer_status(prepared_mat_dir, tmp_path):
    from pipelines.tag_l1 import tag_l1
    tag_l1(SAMPLE, data_root=tmp_path, batch_id="test")
    status = json.loads((prepared_mat_dir / "layer_status.json").read_text())
    assert status.get("l1") == "done"


def test_tag_l1_quality_grade_in_shots(prepared_mat_dir, tmp_path):
    from pipelines.tag_l1 import tag_l1
    tag_l1(SAMPLE, data_root=tmp_path, batch_id="test")
    shots = json.loads((prepared_mat_dir / "shots.json").read_text())
    for shot in shots:
        assert "quality_grade" in shot
        assert shot["quality_grade"] in ("A", "B", "C", "?", None)


def test_tag_l1_emits_business_dimensions(prepared_mat_dir, tmp_path):
    from pipelines.tag_l1 import tag_l1
    tag_l1(SAMPLE, data_root=tmp_path, batch_id="test")
    labels = json.loads((prepared_mat_dir / "labels.json").read_text())
    types = {lb["label_type"] for lb in labels}
    for required in (
        "shot_scale", "quality_grade", "camera_move", "lighting",
        "has_person", "has_dog", "has_product", "has_logo",
        "dog_breed", "fur_color", "subject_layout",
    ):
        assert required in types, f"missing L1 dim {required}"


def test_subject_layout_empty():
    from providers.vision.frame_features import subject_layout
    layout = subject_layout([])
    assert layout["subject_count"] == 0
    assert layout["position"] == "未知"


def test_subject_layout_center():
    from providers.vision.frame_features import subject_layout
    layout = subject_layout([{
        "class_name": "dog",
        "confidence": 0.9,
        "bbox_norm": [0.3, 0.3, 0.7, 0.7],
        "bbox": [0, 0, 1, 1],
    }])
    assert layout["position"] == "中"
    assert layout["subject_count"] == 1
