"""Load and merge config from default.yaml and optional override."""
from pathlib import Path
import yaml

ROOT = Path(__file__).parent.parent  # tag_cut/
_DEFAULT = ROOT / "config" / "default.yaml"
_LOCAL = ROOT / "config" / "local.yaml"


def resolve_config_path(p: object, base: Path = ROOT) -> Path | None:
    """Resolve a config path value; relative values are relative to the tag_cut root."""
    if p is None or p == "" or p == "null":
        return None
    path = Path(str(p)).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def anchor_root(cfg: dict) -> Path:
    """
    Anchor for media paths stored in data JSONs (material file_path, keyframes).

    Convention: stored media paths are relative to the workspace root that holds
    all sibling projects (FeedVideoAssets / FeedVideoMake / pet_cut_tag). That
    root is the parent of the configured asset hub. Without a hub configured,
    fall back to the directory above tag_cut.
    """
    hub = resolve_config_path(cfg.get("asset_hub_root"))
    return hub.parent if hub else ROOT.parent


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
