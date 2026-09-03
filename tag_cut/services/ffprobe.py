"""Thin wrapper around ffprobe for media fact extraction."""
import json
import subprocess
from pathlib import Path


def probe(video_path: Path) -> dict:
    """Run ffprobe and return raw parsed JSON."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed for {video_path}: {e.stderr}") from e
    return json.loads(result.stdout)


def extract_facts(video_path: Path) -> dict:
    """Return L0 media facts dict matching material.schema.json."""
    raw = probe(video_path)
    fmt = raw.get("format", {})
    streams = raw.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    # Parse fps from r_frame_rate "30/1" or "30000/1001"
    fps_raw = video_stream.get("r_frame_rate", "0/1")
    try:
        num, den = fps_raw.split("/")
        fps = round(int(num) / int(den), 3)
    except Exception:
        fps = 0.0

    return {
        "duration": round(float(fmt.get("duration", 0)), 3),
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "fps": fps,
        "codec": video_stream.get("codec_name", ""),
        "has_audio": audio_stream is not None,
    }
