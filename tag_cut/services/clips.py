"""Extract shot clips from source videos with ffmpeg. Never writes into input/."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


class ClipError(RuntimeError):
    """ffmpeg or clip extraction failed."""


def find_shot(data_root: Path, shot_id: str) -> tuple[Path, dict, dict]:
    """
    Locate a shot across all batches.

    Returns (material_dir, shot_dict, material_dict).
    Raises FileNotFoundError if missing.
    """
    if not data_root.exists():
        raise FileNotFoundError(f"data_root not found: {data_root}")
    for batch_dir in data_root.iterdir():
        if not batch_dir.is_dir():
            continue
        for mat_dir in batch_dir.iterdir():
            shots_path = mat_dir / "shots.json"
            material_path = mat_dir / "material.json"
            if not shots_path.exists() or not material_path.exists():
                continue
            shots = json.loads(shots_path.read_text())
            shot = next((s for s in shots if s.get("id") == shot_id), None)
            if shot is None:
                continue
            material = json.loads(material_path.read_text())
            return mat_dir, shot, material
    raise FileNotFoundError(f"shot not found: {shot_id}")


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE).strip("._")
    return cleaned or "clip"


def default_clip_filename(material: dict, shot: dict) -> str:
    stem = Path(str(material.get("file_name") or "clip")).stem
    scene = int(shot.get("scene_number") or 0)
    start = float(shot.get("start_time") or 0)
    end = float(shot.get("end_time") or 0)
    shot_id = str(shot.get("id") or "shot")[:8]
    return _safe_filename(f"{stem}_s{scene:03d}_{start:.2f}-{end:.2f}_{shot_id}.mp4")


def extract_clip(
    src: Path,
    start: float,
    end: float,
    dest: Path,
    *,
    reencode: bool = True,
) -> Path:
    """
    Cut [start, end) from src into dest as mp4.

    Does not modify src. Raises ClipError on ffmpeg failure.
    """
    if not src.exists():
        raise FileNotFoundError(f"source video not found: {src}")
    dest = dest.resolve()
    src_resolved = src.resolve()
    if dest == src_resolved:
        raise ClipError("refusing to overwrite the original video")
    duration = max(0.05, float(end) - float(start))
    dest.parent.mkdir(parents=True, exist_ok=True)

    if reencode:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{float(start):.3f}",
            "-i", str(src_resolved),
            "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-ac", "2",
            "-movflags", "+faststart",
            str(dest),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{float(start):.3f}",
            "-i", str(src_resolved),
            "-t", f"{duration:.3f}",
            "-c", "copy",
            str(dest),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        raise ClipError(result.stderr[-400:] or f"ffmpeg failed for {src}")
    return dest
