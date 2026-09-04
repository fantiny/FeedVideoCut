"""Tests for shot clip extraction and export."""
from pathlib import Path
import json
import pytest

from services.clips import (
    ClipError,
    default_clip_filename,
    extract_clip,
    find_shot,
)

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "input" / "8月第60条信息流" / "v1" / "v1.mp4"
)


def test_find_shot_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_shot(tmp_path, "nope")


def test_find_shot_reads_material(tmp_path):
    mat_dir = tmp_path / "batch" / "mat1"
    mat_dir.mkdir(parents=True)
    (mat_dir / "material.json").write_text(json.dumps({
        "id": "mat1", "file_name": "v1.mp4", "file_path": "/tmp/v1.mp4",
    }))
    (mat_dir / "shots.json").write_text(json.dumps([
        {"id": "shotabc", "start_time": 1.0, "end_time": 2.5, "scene_number": 3},
    ]))
    found_dir, shot, material = find_shot(tmp_path, "shotabc")
    assert found_dir == mat_dir
    assert shot["start_time"] == 1.0
    assert material["file_name"] == "v1.mp4"


def test_default_clip_filename():
    name = default_clip_filename(
        {"file_name": "v1.mp4"},
        {"id": "abcdef123456", "scene_number": 2, "start_time": 1.2, "end_time": 3.4},
    )
    assert name.endswith(".mp4")
    assert "v1" in name
    assert "s002" in name


def test_extract_clip_refuses_overwrite(tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"not-a-real-video")
    with pytest.raises((ClipError, FileNotFoundError)):
        extract_clip(src, 0, 0.2, src)


def test_extract_clip_writes_mp4(tmp_path):
    if not SAMPLE.exists():
        pytest.skip("sample video missing")
    dest = tmp_path / "out" / "clip.mp4"
    extract_clip(SAMPLE, 0.0, 0.4, dest)
    assert dest.exists()
    assert dest.stat().st_size > 1000
