from services.config import load_config

def test_default_config_loads():
    cfg = load_config()
    assert cfg["providers"]["llm"]["cloud_vlm"]["enabled"] is False
    assert cfg["scene_detect"]["threshold"] == 27.0
    assert "l0" in cfg["pipeline"]["layers"]

def test_deep_merge_override(tmp_path):
    override = tmp_path / "override.yaml"
    override.write_text("scene_detect:\n  threshold: 30.0\n")
    cfg = load_config(override)
    assert cfg["scene_detect"]["threshold"] == 30.0
    # other keys preserved
    assert cfg["providers"]["llm"]["cloud_vlm"]["enabled"] is False

def test_top_level_keys_present():
    cfg = load_config()
    for key in ["input_root", "data_root", "exports_root", "scene_detect", "providers", "pipeline"]:
        assert key in cfg, f"Missing key: {key}"

def test_missing_override_raises():
    from pathlib import Path
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/override.yaml"))
