"""Load and merge config from default.yaml and optional override."""
from pathlib import Path
import yaml

_DEFAULT = Path(__file__).parent.parent / "config" / "default.yaml"

def load_config(override_path: Path | None = None) -> dict:
    """Return merged config dict. override_path values win over defaults."""
    cfg = yaml.safe_load(_DEFAULT.read_text())
    if override_path and override_path.exists():
        override = yaml.safe_load(override_path.read_text())
        cfg = _deep_merge(cfg, override)
    return cfg

def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
