"""Load and merge config from default.yaml and optional override."""
from pathlib import Path
import yaml

_DEFAULT = Path(__file__).parent.parent / "config" / "default.yaml"
_LOCAL = Path(__file__).parent.parent / "config" / "local.yaml"


def load_config(override_path: Path | None = None) -> dict:
    """
    Return merged config dict.

    Merge order (later wins): default.yaml → config/local.yaml → override_path.
    local.yaml is used for machine-specific choices (active YOLO weights, etc.).
    """
    cfg = yaml.safe_load(_DEFAULT.read_text()) or {}
    if _LOCAL.exists():
        local = yaml.safe_load(_LOCAL.read_text()) or {}
        cfg = _deep_merge(cfg, local)
    if override_path is not None:
        if not override_path.exists():
            raise FileNotFoundError(f"Config override not found: {override_path}")
        override = yaml.safe_load(override_path.read_text()) or {}
        cfg = _deep_merge(cfg, override)
    return cfg

def _deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
