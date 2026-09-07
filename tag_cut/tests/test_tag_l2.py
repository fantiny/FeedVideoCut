"""Tests for L2 audio event detection and behavior rules."""
from pathlib import Path
import json
import pytest

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "input" / "8月第60条信息流" / "v1" / "v1.mp4"
)

# ---------------------------------------------------------------------------
# Unit tests — behavior rule mapping (no audio/video required)
# ---------------------------------------------------------------------------

from pipelines.tag_l2 import _infer_behaviors


def test_behavior_speech_detected():
    events = [{"event": "speech", "confidence": 0.8}]
    behaviors = _infer_behaviors(events, duration=3.0)
    assert any(b["behavior"] == "人物讲解" for b in behaviors)


def test_behavior_chew_short_is_first_bite():
    events = [{"event": "chew", "confidence": 0.6}]
    behaviors = _infer_behaviors(events, duration=1.2)
    assert any(b["behavior"] == "第一口" for b in behaviors)


def test_behavior_chew_long_is_eating():
    events = [{"event": "chew", "confidence": 0.6}]
    behaviors = _infer_behaviors(events, duration=3.5)
    assert any(b["behavior"] == "大口进食" for b in behaviors)


def test_behavior_silent_long_is_waiting():
    events = [{"event": "silent", "confidence": 0.9}]
    behaviors = _infer_behaviors(events, duration=2.5)
    assert any(b["behavior"] == "等待投喂" for b in behaviors)


def test_behavior_silent_short_is_approaching():
    events = [{"event": "ambient", "confidence": 0.6}]
    behaviors = _infer_behaviors(events, duration=0.8)
    assert any(b["behavior"] == "凑近闻" for b in behaviors)


def test_behavior_no_events_returns_something():
    # Empty audio events still produces a heuristic
    behaviors = _infer_behaviors([], duration=1.0)
    assert isinstance(behaviors, list)


def test_behavior_feed_when_person_bowl_dog():
    behaviors = _infer_behaviors(
        [{"event": "ambient", "confidence": 0.5}],
        duration=1.5,
        has_dog=True,
        has_person=True,
        has_bowl=True,
    )
    assert any(b["behavior"] == "递碗投喂" for b in behaviors)


def test_behavior_look_at_camera_closeup_dog():
    behaviors = _infer_behaviors(
        [{"event": "silent", "confidence": 0.9}],
        duration=0.9,
        has_dog=True,
        shot_scale="特写",
    )
    assert any(b["behavior"] == "抬头看镜头" for b in behaviors)

# ---------------------------------------------------------------------------
# Integration tests — require sample video
# ---------------------------------------------------------------------------

@pytest.fixture
def prepared_mat_dir(tmp_path):
    if not SAMPLE.exists():
        pytest.skip("sample video not found")
    from pipelines.ingest import ingest_video
    from pipelines.split import split_video
    from pipelines.tag_l1 import tag_l1
    ingest_video(SAMPLE, data_root=tmp_path, batch_id="test")
    split_video(SAMPLE, data_root=tmp_path, batch_id="test")
    tag_l1(SAMPLE, data_root=tmp_path, batch_id="test")
    from services.config import anchor_root, load_config
    from services.paths import material_id, ensure_material_dir
    from services.config import load_config
    mat_id = material_id(SAMPLE, anchor_root(load_config()))
    return ensure_material_dir(tmp_path, "test", mat_id)


def test_tag_l2_creates_l2_labels(prepared_mat_dir, tmp_path):
    from pipelines.tag_l2 import tag_l2
    tag_l2(SAMPLE, data_root=tmp_path, batch_id="test")
    labels = json.loads((prepared_mat_dir / "labels.json").read_text())
    l2 = [lb for lb in labels if lb["layer"] == "l2"]
    assert len(l2) > 0


def test_tag_l2_label_fields(prepared_mat_dir, tmp_path):
    from pipelines.tag_l2 import tag_l2
    tag_l2(SAMPLE, data_root=tmp_path, batch_id="test")
    labels = json.loads((prepared_mat_dir / "labels.json").read_text())
    l2 = [lb for lb in labels if lb["layer"] == "l2"]
    for label in l2:
        for key in ["id", "shot_id", "layer", "label_type", "label_value", "source", "confidence"]:
            assert key in label
        assert label["label_type"] in (
            "audio_event", "behavior", "audio_texture", "audio_role",
        )


def test_tag_l2_layer_status(prepared_mat_dir, tmp_path):
    from pipelines.tag_l2 import tag_l2
    tag_l2(SAMPLE, data_root=tmp_path, batch_id="test")
    status = json.loads((prepared_mat_dir / "layer_status.json").read_text())
    assert status.get("l2") == "done"
