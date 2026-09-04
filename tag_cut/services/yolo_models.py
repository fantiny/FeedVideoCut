"""
YOLO model catalog, local env probe, download, and active-weight selection.

Weights are stored under tag_cut/models/. Active path is persisted in
config/local.yaml so stronger machines can switch to larger checkpoints.
"""
from __future__ import annotations

import platform
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
LOCAL_CFG = PROJECT_ROOT / "config" / "local.yaml"
DEFAULT_CFG = PROJECT_ROOT / "config" / "default.yaml"

# Official Ultralytics release assets (COCO detect).
# See https://docs.ultralytics.com/models/yolov8/
ASSET_BASE_V8 = "https://github.com/ultralytics/assets/releases/download/v8.4.0"
ASSET_BASE_V11 = "https://github.com/ultralytics/assets/releases/download/v8.3.0"

_download_lock = threading.Lock()
_download_state: dict[str, dict[str, Any]] = {}


@dataclass(frozen=True)
class ModelSpec:
    id: str
    filename: str
    family: str
    size_class: str  # n/s/m/l/x
    params_m: float
    approx_mb: int
    url: str
    description: str
    min_ram_gb_supported: float
    min_ram_gb_recommended: float


CATALOG: list[ModelSpec] = [
    ModelSpec(
        "yolov8n", "yolov8n.pt", "YOLOv8", "n", 3.2, 6,
        f"{ASSET_BASE_V8}/yolov8n.pt",
        "Nano — 本机默认推荐，速度快、显存占用低",
        4, 8,
    ),
    ModelSpec(
        "yolov8s", "yolov8s.pt", "YOLOv8", "s", 11.2, 22,
        f"{ASSET_BASE_V8}/yolov8s.pt",
        "Small — 精度更好，16GB 机器通常可用",
        8, 12,
    ),
    ModelSpec(
        "yolov8m", "yolov8m.pt", "YOLOv8", "m", 25.9, 50,
        f"{ASSET_BASE_V8}/yolov8m.pt",
        "Medium — 精度更高，建议 ≥16GB 且有加速器",
        12, 16,
    ),
    ModelSpec(
        "yolov8l", "yolov8l.pt", "YOLOv8", "l", 43.7, 87,
        f"{ASSET_BASE_V8}/yolov8l.pt",
        "Large — 适合性能更好的工作站",
        16, 24,
    ),
    ModelSpec(
        "yolov8x", "yolov8x.pt", "YOLOv8", "x", 68.2, 136,
        f"{ASSET_BASE_V8}/yolov8x.pt",
        "XLarge — 最高精度，建议高性能 GPU / ≥32GB",
        24, 32,
    ),
    ModelSpec(
        "yolo11n", "yolo11n.pt", "YOLO11", "n", 2.6, 5,
        f"{ASSET_BASE_V11}/yolo11n.pt",
        "YOLO11 Nano — 新一代轻量检测",
        4, 8,
    ),
    ModelSpec(
        "yolo11s", "yolo11s.pt", "YOLO11", "s", 9.4, 19,
        f"{ASSET_BASE_V11}/yolo11s.pt",
        "YOLO11 Small",
        8, 12,
    ),
    ModelSpec(
        "yolo11m", "yolo11m.pt", "YOLO11", "m", 20.1, 39,
        f"{ASSET_BASE_V11}/yolo11m.pt",
        "YOLO11 Medium",
        12, 16,
    ),
]


def catalog_by_id(model_id: str) -> ModelSpec | None:
    for m in CATALOG:
        if m.id == model_id or m.filename == model_id:
            return m
    return None


def models_dir() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR


def probe_environment() -> dict[str, Any]:
    """Detect local hardware / runtime for model support scoring."""
    ram_gb = 0.0
    try:
        import psutil  # type: ignore[import]
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except ImportError:
        if platform.system() == "Darwin":
            import subprocess
            try:
                out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
                ram_gb = round(int(out) / (1024 ** 3), 1)
            except Exception:  # noqa: BLE001
                ram_gb = 0.0

    accelerator = "cpu"
    torch_version = None
    mps = False
    cuda = False
    try:
        import torch  # type: ignore[import]
        torch_version = torch.__version__
        cuda = bool(torch.cuda.is_available())
        mps = bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
        if cuda:
            accelerator = "cuda"
        elif mps:
            accelerator = "mps"
    except ImportError:
        pass

    ultralytics_ok = False
    try:
        import ultralytics  # type: ignore[import]  # noqa: F401
        ultralytics_ok = True
    except ImportError:
        pass

    cpu = platform.processor() or platform.machine()
    if platform.system() == "Darwin":
        import subprocess
        try:
            cpu = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
            ).strip() or cpu
        except Exception:  # noqa: BLE001
            pass

    return {
        "os": platform.system(),
        "arch": platform.machine(),
        "cpu": cpu,
        "ram_gb": ram_gb,
        "accelerator": accelerator,
        "torch_version": torch_version,
        "cuda": cuda,
        "mps": mps,
        "ultralytics": ultralytics_ok,
        "models_dir": str(models_dir()),
    }


def score_model(spec: ModelSpec, env: dict[str, Any]) -> dict[str, Any]:
    ram = float(env.get("ram_gb") or 0)
    accel = env.get("accelerator") or "cpu"
    has_accel = accel in ("mps", "cuda")
    ultralytics_ok = bool(env.get("ultralytics"))

    supported = True
    recommended = False
    reasons: list[str] = []

    if not ultralytics_ok:
        supported = False
        reasons.append("未安装 ultralytics")
    if ram and ram < spec.min_ram_gb_supported:
        supported = False
        reasons.append(f"内存 {ram}GB < 最低 {spec.min_ram_gb_supported}GB")
    elif ram and ram < spec.min_ram_gb_recommended:
        reasons.append(f"内存偏低（建议 ≥{spec.min_ram_gb_recommended}GB）")
    if spec.size_class in ("l", "x") and not has_accel:
        supported = supported and ram >= spec.min_ram_gb_supported + 4
        reasons.append("大模型在纯 CPU 上很慢")
    if supported and ram >= spec.min_ram_gb_recommended and (
        spec.size_class in ("n", "s") or (has_accel and spec.size_class == "m")
    ):
        recommended = True
    if supported and not recommended and not reasons:
        reasons.append("可用，但非本机首选")
    if recommended and not reasons:
        reasons.append("适合当前机器")

    # Prefer nano as default recommendation on Apple Silicon ≤16GB
    if recommended and spec.size_class == "n" and ram and ram <= 16:
        reasons = ["本机默认推荐（轻量 + MPS/CPU 友好）"]

    return {
        "supported": supported,
        "recommended": recommended and supported,
        "reasons": reasons,
        "badge": (
            "recommended" if recommended and supported else
            "supported" if supported else
            "unsupported"
        ),
    }


def active_weights_relpath() -> str:
    from services.config import load_config
    cfg = load_config()
    return str(cfg.get("providers", {}).get("vision", {}).get("yolo_weights") or "models/yolov8n.pt")


def active_weights_path() -> Path:
    rel = active_weights_relpath()
    p = Path(rel)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


def set_active_model(model_id: str) -> dict[str, Any]:
    spec = catalog_by_id(model_id)
    if not spec:
        raise ValueError(f"unknown model: {model_id}")
    dest = models_dir() / spec.filename
    if not dest.exists():
        raise FileNotFoundError(f"model not downloaded: {spec.filename}")

    rel = f"models/{spec.filename}"
    prev: dict = {}
    if LOCAL_CFG.exists():
        prev = yaml.safe_load(LOCAL_CFG.read_text()) or {}
    merged = dict(prev)
    providers = dict(merged.get("providers") or {})
    vision = dict(providers.get("vision") or {})
    vision["yolo_weights"] = rel
    providers["vision"] = vision
    merged["providers"] = providers
    LOCAL_CFG.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_CFG.write_text(yaml.safe_dump(merged, allow_unicode=True, sort_keys=False))
    return {"active": rel, "path": str(dest), "model_id": spec.id}


def download_status(model_id: str) -> dict[str, Any]:
    return dict(_download_state.get(model_id) or {"status": "idle"})


def download_model(model_id: str, force: bool = False) -> dict[str, Any]:
    """
    Download weights into models/. Synchronous; safe to call from a worker thread.
    """
    spec = catalog_by_id(model_id)
    if not spec:
        raise ValueError(f"unknown model: {model_id}")

    dest = models_dir() / spec.filename
    if dest.exists() and dest.stat().st_size > 1_000_000 and not force:
        _download_state[spec.id] = {
            "status": "done", "path": str(dest), "bytes": dest.stat().st_size,
        }
        return _download_state[spec.id]

    with _download_lock:
        _download_state[spec.id] = {"status": "downloading", "path": str(dest), "bytes": 0}
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            import httpx
            with httpx.stream("GET", spec.url, follow_redirects=True, timeout=120.0) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length") or 0)
                written = 0
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=1024 * 256):
                        f.write(chunk)
                        written += len(chunk)
                        _download_state[spec.id] = {
                            "status": "downloading",
                            "path": str(dest),
                            "bytes": written,
                            "total": total or None,
                        }
            tmp.replace(dest)
            _download_state[spec.id] = {
                "status": "done", "path": str(dest), "bytes": dest.stat().st_size,
            }
            return _download_state[spec.id]
        except Exception as exc:  # noqa: BLE001
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            # Fallback: ultralytics auto-download then move
            try:
                from ultralytics import YOLO  # type: ignore[import]
                # YOLO downloads into CWD; run inside models_dir
                prev_cwd = Path.cwd()
                try:
                    import os
                    os.chdir(models_dir())
                    YOLO(spec.filename)
                finally:
                    os.chdir(prev_cwd)
                if not dest.exists():
                    # ultralytics may place in weights_dir
                    alt = Path.cwd() / spec.filename
                    if alt.exists():
                        alt.replace(dest)
                if dest.exists():
                    _download_state[spec.id] = {
                        "status": "done", "path": str(dest), "bytes": dest.stat().st_size,
                    }
                    return _download_state[spec.id]
                raise RuntimeError(f"download failed: {exc}") from exc
            except Exception as exc2:  # noqa: BLE001
                _download_state[spec.id] = {"status": "failed", "error": str(exc2)}
                raise


def list_models_with_status() -> dict[str, Any]:
    env = probe_environment()
    active = active_weights_path()
    active_name = active.name if active.exists() or active_weights_relpath() else ""
    items = []
    for spec in CATALOG:
        path = models_dir() / spec.filename
        score = score_model(spec, env)
        dl = download_status(spec.id)
        items.append({
            **asdict(spec),
            "local_path": str(path),
            "downloaded": path.exists() and path.stat().st_size > 1_000_000,
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "active": active_name == spec.filename or active_weights_relpath().endswith(spec.filename),
            "download": dl,
            **score,
        })

    # Exactly one recommended badge: prefer nano on ≤16GB, else best supported size.
    recommended_id = None
    ram = float(env.get("ram_gb") or 0)
    prefer_order = ["yolov8n", "yolo11n", "yolov8s", "yolo11s", "yolov8m", "yolo11m", "yolov8l", "yolov8x"]
    if ram >= 24:
        prefer_order = ["yolov8m", "yolo11m", "yolov8s", "yolo11s", "yolov8n", "yolo11n", "yolov8l", "yolov8x"]
    elif ram >= 16:
        prefer_order = ["yolov8n", "yolo11n", "yolov8s", "yolo11s", "yolov8m", "yolo11m", "yolov8l", "yolov8x"]
    by_id = {i["id"]: i for i in items}
    for mid in prefer_order:
        row = by_id.get(mid)
        if row and row["supported"]:
            recommended_id = mid
            break
    if not recommended_id:
        recommended_id = next((i["id"] for i in items if i["supported"]), items[0]["id"] if items else None)

    for i in items:
        i["recommended"] = i["id"] == recommended_id
        if i["recommended"]:
            i["badge"] = "recommended"
            if not i["reasons"] or i["reasons"] == ["可用，但非本机首选"]:
                i["reasons"] = ["本机默认推荐"]
        elif i["supported"] and i["badge"] == "recommended":
            i["badge"] = "supported"

    return {
        "environment": env,
        "active_weights": active_weights_relpath(),
        "recommended_id": recommended_id,
        "models": items,
    }


def ensure_recommended_downloaded() -> dict[str, Any]:
    """Download the recommended model for this machine if missing."""
    listing = list_models_with_status()
    rid = listing.get("recommended_id") or "yolov8n"
    result = download_model(rid)
    # Activate if nothing active on disk
    active = active_weights_path()
    if not active.exists():
        set_active_model(rid)
    return {"recommended_id": rid, "download": result, "active": active_weights_relpath()}
