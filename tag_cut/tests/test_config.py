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
