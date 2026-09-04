"""Tests for YOLO catalog / env scoring / activate."""
from pathlib import Path
import yaml

from services.yolo_models import (
    CATALOG,
    catalog_by_id,
    list_models_with_status,
    probe_environment,
    score_model,
    set_active_model,
)


def test_catalog_has_nano():
    assert catalog_by_id("yolov8n") is not None
    assert any(m.id == "yolov8n" for m in CATALOG)


def test_probe_environment_has_core_fields():
    env = probe_environment()
    for key in ("os", "arch", "ram_gb", "accelerator", "ultralytics", "models_dir"):
        assert key in env


def test_score_nano_recommended_on_16gb_mps():
    env = {
        "ram_gb": 16.0,
        "accelerator": "mps",
        "ultralytics": True,
    }
    nano = catalog_by_id("yolov8n")
    assert nano is not None
    score = score_model(nano, env)
    assert score["supported"] is True
    assert score["recommended"] is True


def test_score_xlarge_not_recommended_on_16gb():
    env = {"ram_gb": 16.0, "accelerator": "mps", "ultralytics": True}
    x = catalog_by_id("yolov8x")
    assert x is not None
    score = score_model(x, env)
    assert score["recommended"] is False


def test_list_models_includes_badges():
    data = list_models_with_status()
    assert "models" in data and "environment" in data
    assert data["recommended_id"]
    row = data["models"][0]
    assert "badge" in row and "supported" in row


def test_activate_requires_download(tmp_path, monkeypatch):
    import services.yolo_models as ym
    monkeypatch.setattr(ym, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(ym, "LOCAL_CFG", tmp_path / "local.yaml")
    try:
        set_active_model("yolov8n")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
    # create fake weight
    (tmp_path / "yolov8n.pt").write_bytes(b"x" * 2_000_000)
    out = set_active_model("yolov8n")
    assert out["model_id"] == "yolov8n"
    cfg = yaml.safe_load((tmp_path / "local.yaml").read_text())
    assert cfg["providers"]["vision"]["yolo_weights"] == "models/yolov8n.pt"
