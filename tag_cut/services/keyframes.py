"""Extract keyframes from a video at specific timestamps."""
import subprocess
from pathlib import Path


def extract_keyframe(
    video_path: Path,
    timestamp: float,
    output_path: Path,
    quality: int = 2,
) -> Path:
    """
    Extract a single frame at `timestamp` seconds from `video_path`.
    Saves as JPEG to `output_path`. Returns output_path.
    `quality` is ffmpeg -q:v (1=best, 31=worst; 2 is visually lossless).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", str(quality),
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg keyframe failed at {timestamp}s for {video_path}: {result.stderr[-300:]}")
    return output_path
