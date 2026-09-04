"""Tests for tag search across batch labels."""
import json
from pathlib import Path

from services.search import search_labels, list_label_facets


def _seed(data_root: Path) -> None:
    mat = data_root / "b1" / "mat1"
    mat.mkdir(parents=True)
    (mat / "material.json").write_text(json.dumps({
        "id": "mat1", "file_name": "v1.mp4", "file_path": "/tmp/v1.mp4",
    }, ensure_ascii=False))
    (mat / "shots.json").write_text(json.dumps([
        {"id": "shotA", "start_time": 0.0, "end_time": 1.2, "key_frames": {"mid": ""}},
        {"id": "shotB", "start_time": 1.2, "end_time": 3.0, "key_frames": {"mid": ""}},
    ]))
    (mat / "labels.json").write_text(json.dumps([
        {"shot_id": "shotA", "layer": "l2", "label_type": "behavior",
         "label_value": "第一口", "confidence": 0.7, "source": "rule"},
        {"shot_id": "shotB", "layer": "l4", "label_type": "applicable_types",
         "label_value": ["种草", "分享"], "confidence": 0.6, "source": "rule"},
        {"shot_id": "shotB", "layer": "l1", "label_type": "shot_scale",
         "label_value": "特写", "confidence": 0.8, "source": "rule"},
    ], ensure_ascii=False))


def test_search_by_behavior(tmp_path):
    _seed(tmp_path)
    out = search_labels(tmp_path, "第一口")
    assert out["count"] == 1
    assert out["hits"][0]["shot_id"] == "shotA"


def test_search_skips_nested_edit_value_noise(tmp_path):
    """Query should hit lighting=自然光, not every edit_value that embeds lighting."""
    mat = tmp_path / "b1" / "mat1"
    mat.mkdir(parents=True)
    (mat / "material.json").write_text(json.dumps({
        "id": "mat1", "file_name": "v1.mp4", "file_path": "/tmp/v1.mp4",
    }))
    (mat / "shots.json").write_text(json.dumps([
        {"id": "shotA", "start_time": 0.0, "end_time": 1.0, "key_frames": {}},
        {"id": "shotB", "start_time": 1.0, "end_time": 2.0, "key_frames": {}},
    ]))
    (mat / "labels.json").write_text(json.dumps([
        {"shot_id": "shotA", "layer": "l1", "label_type": "lighting",
         "label_value": "自然光", "confidence": 0.5, "source": "rule"},
        {"shot_id": "shotB", "layer": "l5", "label_type": "edit_value",
         "label_value": {"lighting": "自然光", "loop_value": False},
         "confidence": 0.5, "source": "rule"},
    ], ensure_ascii=False))
    out = search_labels(tmp_path, "自然")
    assert out["count"] == 1
    assert out["hits"][0]["shot_id"] == "shotA"



def test_search_by_applicable_type(tmp_path):
    _seed(tmp_path)
    out = search_labels(tmp_path, "种草")
    assert out["count"] == 1
    assert out["hits"][0]["shot_id"] == "shotB"


def test_search_filter_label_type(tmp_path):
    _seed(tmp_path)
    out = search_labels(tmp_path, "特写", label_type="shot_scale")
    assert out["count"] == 1
    out2 = search_labels(tmp_path, "特写", label_type="behavior")
    assert out2["count"] == 0


def test_facets_lists_types(tmp_path):
    _seed(tmp_path)
    facets = list_label_facets(tmp_path, batch_id="b1")
    types = {t["type"] for t in facets["label_types"]}
    assert "behavior" in types
    assert "shot_scale" in types
