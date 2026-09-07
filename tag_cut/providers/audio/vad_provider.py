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


def _speech_likelihood(samples: list[int], sr: int = 16000) -> float:
    """
    Speech likelihood (0–1) via syllabic modulation of the energy envelope.

    Human speech modulates its loudness at ~2–8 Hz (syllables); music/ambience
    is steadier and barks are sparse bursts. We build a 25 ms RMS envelope and
    measure how much of its variance sits in that band (zero crossings of the
    mean-removed envelope per second, clipped to the speech band).
    """
    if not samples:
        return 0.0
    hop = sr // 40  # 25 ms
    n = len(samples) // hop
    if n < 8:
        return 0.0
    env = [math.sqrt(sum(s * s for s in samples[i * hop:(i + 1) * hop]) / hop) for i in range(n)]
    mean_env = sum(env) / n
    if mean_env < 200:  # near-silent
        return 0.0
    norm = [e - mean_env for e in env]
    # zero-crossing rate of the mean-removed envelope → modulation frequency
    crossings = sum(1 for i in range(1, n) if (norm[i] >= 0) != (norm[i - 1] >= 0))
    mod_hz = crossings / 2 / (n * hop / sr)
    # speech syllables live at 2–8 Hz; weight peak response inside the band
    if 2.0 <= mod_hz <= 8.0:
        band_factor = 1.0
    elif 1.0 <= mod_hz < 2.0:
        band_factor = (mod_hz - 1.0)
    elif 8.0 < mod_hz <= 12.0:
        band_factor = max(0.0, (12.0 - mod_hz) / 4.0)
    else:
        band_factor = 0.0
    # how strongly the envelope fluctuates at all
    var = sum(v * v for v in norm) / n
    mod_depth = min(1.0, (math.sqrt(var) / mean_env) * 1.5)
    return round(min(1.0, band_factor * mod_depth), 3)


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
        speech_like = _speech_likelihood(samples)

        events: list[dict] = []

        # RMS threshold: 32768 is max for 16-bit audio
        if rms < 200:
            events.append({"event": "silent", "confidence": 0.85, "source": "rule"})
            return events

        # Speech detection first: syllabic modulation is the strongest signal.
        # (P0-3: 人声解说漏标是制作侧原声穿帮的根因)
        if speech_like >= 0.35:
            events.append({
                "event": "speech",
                "confidence": round(max(0.6, min(0.95, speech_like)), 2),
                "source": "rule_vad",
            })

        # ZCR heuristics (secondary):
        # High ZCR + high energy → bark / sharp sound
        # Low ZCR + medium energy → chew/lick (low-freq)
        # Very low ZCR + medium energy → ambient / low rumble
        if zcr > 0.15 and speech_like < 0.45:
            events.append({"event": "bark", "confidence": round(min(0.9, zcr * 4), 2), "source": "rule"})
        elif 0.02 < zcr <= 0.05 and speech_like < 0.3:
            events.append({"event": "chew", "confidence": 0.55, "source": "rule"})
        elif not events or (zcr <= 0.02 and speech_like < 0.2):
            events.append({"event": "ambient", "confidence": 0.6, "source": "rule"})

        return events

    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass
