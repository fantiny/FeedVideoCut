"""Tests for L3–L6 scoring (rule scorer + cloud VLM config)."""
from pathlib import Path
import json
import pytest

from providers.llm.rule_scorer import score_shot
from providers.llm.cloud_vlm import CloudVLMProvider
from services.config import load_config

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "input" / "8月第60条信息流" / "v1" / "v1.mp4"
)

# ---------------------------------------------------------------------------
# Unit tests — rule scorer (no video required)
# ---------------------------------------------------------------------------

def _make_shot(shot_id: str = "abc123", duration: float = 2.0) -> dict:
    return {
        "id": shot_id,
        "start_time": 0.0,
        "end_time": duration,
        "quality_grade": "A",
        "key_frames": {},
    }


def test_rule_scorer_returns_labels_and_scores():
    shot = _make_shot()
    labels: list[dict] = []
    new_labels, scores = score_shot(shot, labels)
    assert isinstance(new_labels, list)
    assert isinstance(scores, dict)
    assert "hook_score" in scores
    assert "shot_id" in scores


def test_rule_scorer_applicable_types_present():
    shot = _make_shot()
    labels = [
        {"shot_id": "abc123", "layer": "l2", "label_type": "behavior",
         "label_value": "第一口", "source": "rule", "confidence": 0.6},
    ]
    new_labels, scores = score_shot(shot, labels)
    type_labels = [lb for lb in new_labels if lb["label_type"] == "applicable_types"]
    assert len(type_labels) == 1
    assert "种草" in type_labels[0]["label_value"]


def test_rule_scorer_high_hook_for_first_bite_closeup():
    shot = _make_shot()
    labels = [
        {"shot_id": "abc123", "layer": "l1", "label_type": "shot_scale",
         "label_value": "大特写", "source": "rule", "confidence": 0.9},
        {"shot_id": "abc123", "layer": "l2", "label_type": "behavior",
         "label_value": "第一口", "source": "rule", "confidence": 0.7},
    ]
    _, scores = score_shot(shot, labels)
    assert scores["hook_score"] >= 0.7


def test_rule_scorer_emits_expanded_business_dims():
    shot = _make_shot(duration=1.2)
    labels = [
        {"shot_id": "abc123", "layer": "l1", "label_type": "has_dog",
         "label_value": "是", "source": "rule", "confidence": 0.8},
        {"shot_id": "abc123", "layer": "l1", "label_type": "has_bowl",
         "label_value": "是", "source": "rule", "confidence": 0.7},
        {"shot_id": "abc123", "layer": "l1", "label_type": "shot_scale",
         "label_value": "特写", "source": "rule", "confidence": 0.8},
        {"shot_id": "abc123", "layer": "l1", "label_type": "camera_move",
         "label_value": "固定", "source": "rule", "confidence": 0.6},
        {"shot_id": "abc123", "layer": "l2", "label_type": "behavior",
         "label_value": "大口进食", "source": "rule", "confidence": 0.7},
        {"shot_id": "abc123", "layer": "l2", "label_type": "audio_event",
         "label_value": "chew", "source": "rule", "confidence": 0.6},
    ]
    new_labels, scores = score_shot(shot, labels)
    types = {lb["label_type"] for lb in new_labels}
    for required in (
        "relation_hint", "behavior_chain", "subject_role",
        "category_code", "emotion", "emotion_intensity",
        "commercial_evidence", "hook_role", "content_intent",
        "edit_value", "usable_duration", "platform_fit", "compliance",
    ):
        assert required in types, f"missing dim {required}"
    assert scores["evidence_score"] >= 0.5
    cat = next(lb for lb in new_labels if lb["label_type"] == "category_code")
    assert cat["label_value"] == "V03_狗狗进食"


def test_cloud_disabled_by_default():
    cfg = load_config()
    assert cfg["providers"]["llm"]["cloud_vlm"]["enabled"] is False


def test_cloud_provider_noop_when_disabled(tmp_path):
    cfg = load_config()
    provider = CloudVLMProvider(cfg)
    assert not provider.enabled
    result = provider.enhance("shot_id_x", [], [])
    assert result == []


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
    from pipelines.tag_l2 import tag_l2
    ingest_video(SAMPLE, data_root=tmp_path, batch_id="test")
    split_video(SAMPLE, data_root=tmp_path, batch_id="test")
    tag_l1(SAMPLE, data_root=tmp_path, batch_id="test")
    tag_l2(SAMPLE, data_root=tmp_path, batch_id="test")
    from services.paths import material_id, ensure_material_dir
    return ensure_material_dir(tmp_path, "test", material_id(SAMPLE))


def test_tag_l3_l6_creates_scores(prepared_mat_dir, tmp_path):
    from pipelines.tag_l3_l6 import tag_l3_l6
    tag_l3_l6(SAMPLE, data_root=tmp_path, batch_id="test")
    scores = json.loads((prepared_mat_dir / "scores.json").read_text())
    assert isinstance(scores, list) and len(scores) > 0
    for s in scores:
        assert "hook_score" in s and "shot_id" in s


def test_tag_l3_l6_creates_l3_to_l6_labels(prepared_mat_dir, tmp_path):
    from pipelines.tag_l3_l6 import tag_l3_l6
    tag_l3_l6(SAMPLE, data_root=tmp_path, batch_id="test")
    labels = json.loads((prepared_mat_dir / "labels.json").read_text())
    high_layers = [lb for lb in labels if lb.get("layer") in ("l3", "l4", "l5", "l6")]
    assert len(high_layers) > 0


def test_tag_l3_l6_layer_status(prepared_mat_dir, tmp_path):
    from pipelines.tag_l3_l6 import tag_l3_l6
    tag_l3_l6(SAMPLE, data_root=tmp_path, batch_id="test")
    status = json.loads((prepared_mat_dir / "layer_status.json").read_text())
    assert status.get("l3_l6") == "done"
