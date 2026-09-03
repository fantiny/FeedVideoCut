"""
Cloud VLM provider for L3–L6 enhancement.

Default: disabled (config providers.llm.cloud_vlm.enabled = false).
When enabled, sends keyframes + existing labels to an OpenAI-compatible
vision endpoint and merges returned labels.

Input sent to cloud:
  - Up to max_frames_per_shot keyframes (base64 JPEG)
  - Time range and existing label summary
  - Task prompt

NOT sent: full video, file paths, business secrets.

Cache: SHA-1 keyed by (shot_id, frame mtimes, prompt_version).
"""
from __future__ import annotations

import base64
import hashlib
import json
import warnings
from pathlib import Path

# Cache lives in memory for process lifetime; future: use Redis or file cache
_CACHE: dict[str, list[dict]] = {}

PROMPT_VERSION = "v1"

_SYSTEM_PROMPT = """You are a pet food short-video shot analyst.
Given keyframes from a single video shot, analyse the visual and contextual information.
Return a JSON array of label objects. Each object must have:
  label_type: string (e.g. "behavior_chain", "subject_relation", "commercial_evidence")
  label_value: any JSON value
  confidence: float 0-1
  reasoning: string (1 sentence)
Only return the JSON array, no other text."""


def _cache_key(shot_id: str, frame_paths: list[Path]) -> str:
    parts = [shot_id, PROMPT_VERSION]
    for p in frame_paths:
        if p.exists():
            parts.append(str(p.stat().st_mtime))
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


class CloudVLMProvider:
    """
    Optional cloud VLM provider. No-ops when disabled or misconfigured.
    """

    def __init__(self, cfg: dict):
        vlm_cfg = cfg.get("providers", {}).get("llm", {}).get("cloud_vlm", {})
        self._enabled: bool = bool(vlm_cfg.get("enabled", False))
        self._api_base: str = vlm_cfg.get("api_base", "https://api.openai.com/v1")
        self._api_key_env: str = vlm_cfg.get("api_key_env", "OPENAI_API_KEY")
        self._model: str = vlm_cfg.get("model", "gpt-4o")
        self._conf_threshold: float = float(vlm_cfg.get("confidence_threshold", 0.6))
        self._max_frames: int = int(vlm_cfg.get("max_frames_per_shot", 3))
        self._use_cache: bool = bool(vlm_cfg.get("cache", True))

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enhance(
        self,
        shot_id: str,
        keyframe_paths: list[Path],
        existing_labels: list[dict],
        prompt_hint: str = "",
    ) -> list[dict]:
        """
        Returns new label dicts (source='cloud_vlm') or [] if disabled/error.
        """
        if not self._enabled:
            return []

        import os
        api_key = os.environ.get(self._api_key_env, "")
        if not api_key:
            warnings.warn(
                f"cloud_vlm enabled but {self._api_key_env} not set — skipping."
            )
            return []

        # Select frames to send
        frames = [p for p in keyframe_paths if p and p.exists()][: self._max_frames]
        if not frames:
            return []

        # Cache check
        ck = _cache_key(shot_id, frames)
        if self._use_cache and ck in _CACHE:
            return _CACHE[ck]

        try:
            import httpx  # type: ignore[import]
        except ImportError:
            warnings.warn("httpx not installed — cloud VLM unavailable.")
            return []

        # Build message
        label_summary = json.dumps(
            [{"type": lb["label_type"], "value": lb["label_value"]}
             for lb in existing_labels],
            ensure_ascii=False,
        )
        user_content: list[dict] = [
            {"type": "text", "text": (
                f"Shot id: {shot_id}\n"
                f"Existing labels: {label_summary}\n"
                f"Hint: {prompt_hint or 'Analyse shot content.'}"
            )},
        ]
        for p in frames:
            b64 = _encode_image(p)
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"},
            })

        try:
            resp = httpx.post(
                f"{self._api_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": 512,
                },
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            raw_labels = json.loads(content)
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"cloud_vlm call failed for shot {shot_id}: {exc}")
            return []

        # Filter by confidence threshold and attach metadata
        result: list[dict] = []
        for lb in raw_labels:
            if not isinstance(lb, dict):
                continue
            conf = float(lb.get("confidence", 0))
            if conf < self._conf_threshold:
                continue
            result.append({
                "shot_id": shot_id,
                "layer": "l3",  # cloud VLM always contributes to L3+ understanding
                "label_type": lb.get("label_type", "vlm_tag"),
                "label_value": lb.get("label_value"),
                "source": "cloud_vlm",
                "confidence": conf,
            })

        if self._use_cache:
            _CACHE[ck] = result
        return result
