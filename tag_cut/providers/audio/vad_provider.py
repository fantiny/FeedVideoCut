"""
Audio event detection provider (L2).

Strategy (v1, no ML dependency):
  - Extract per-shot audio WAV via ffmpeg
  - Compute RMS energy → detect if speech/sound is present
  - Simple zero-crossing rate heuristic to distinguish bark/chew from ambient

Event labels (对齐设计文档 SOP):
  speech    人声
  bark      犬叫
  chew      咀嚼
  lick      舔食
  ambient   环境音
  silent    无声
"""
from __future__ import annotations

import math
import subprocess
import tempfile
import warnings
from pathlib import Path


def _extract_shot_wav(video_path: Path, start: float, end: float, wav_path: Path) -> bool:
    """Extract audio segment to WAV. Returns True on success."""
    duration = max(0.1, end - start)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(start), "-t", str(duration),
        "-i", str(video_path),
        "-ac", "1", "-ar", "16000",  # mono 16 kHz
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def _read_wav_pcm(wav_path: Path) -> list[int] | None:
    """Read raw PCM samples from a 16-bit mono WAV. Returns None on error."""
    import struct
    try:
        data = wav_path.read_bytes()
        # Minimal WAV header parse: data chunk starts at byte 44 for standard PCM
        if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            return None
        # Find "data" chunk
        idx = 12
        while idx < len(data) - 8:
            chunk_id = data[idx:idx+4]
            chunk_size = struct.unpack_from("<I", data, idx+4)[0]
            if chunk_id == b"data":
                samples_bytes = data[idx+8: idx+8+chunk_size]
                n = len(samples_bytes) // 2
                return list(struct.unpack_from(f"<{n}h", samples_bytes))
            idx += 8 + chunk_size
        return None
    except Exception:
        return None


def _compute_rms(samples: list[int]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


def _compute_zcr(samples: list[int]) -> float:
    """Zero-crossing rate (normalised 0–1)."""
    if len(samples) < 2:
        return 0.0
    crossings = sum(
        1 for i in range(1, len(samples))
        if (samples[i] >= 0) != (samples[i - 1] >= 0)
    )
    return crossings / len(samples)


def detect_audio_events(
    video_path: Path,
    start: float,
    end: float,
) -> list[dict]:
    """
    Detect audio events for a single shot [start, end].

    Returns list of event dicts:
      {"event": str, "confidence": float, "source": "rule"}
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)

    try:
        if not _extract_shot_wav(video_path, start, end, wav_path):
            warnings.warn(f"Audio extraction failed for shot [{start:.2f}-{end:.2f}]")
            return []

        samples = _read_wav_pcm(wav_path)
        if samples is None:
            return []

        rms = _compute_rms(samples)
        zcr = _compute_zcr(samples)

        events: list[dict] = []

        # RMS threshold: 32768 is max for 16-bit audio
        if rms < 200:
            events.append({"event": "silent", "confidence": 0.85, "source": "rule"})
            return events

        # ZCR heuristics:
        # High ZCR + high energy → bark / sharp sound
        # Medium ZCR → speech
        # Low ZCR + medium energy → ambient / low rumble
        # Very low ZCR + medium energy → chew/lick (low-freq)
        if zcr > 0.15:
            events.append({"event": "bark", "confidence": round(min(0.9, zcr * 4), 2), "source": "rule"})
        elif 0.05 < zcr <= 0.15:
            conf = round(min(0.85, rms / 8000), 2)
            events.append({"event": "speech", "confidence": conf, "source": "rule"})
        elif 0.02 < zcr <= 0.05:
            events.append({"event": "chew", "confidence": 0.55, "source": "rule"})
        else:
            events.append({"event": "ambient", "confidence": 0.6, "source": "rule"})

        return events

    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass
