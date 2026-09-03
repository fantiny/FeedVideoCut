"""Base protocol for LLM/VLM providers."""
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class VLMProvider(Protocol):
    """Visual Language Model provider for L3–L6 enhancement."""

    @property
    def enabled(self) -> bool:
        """Whether the provider is active (config-controlled)."""
        ...

    def enhance(
        self,
        shot_id: str,
        keyframe_paths: list[Path],
        existing_labels: list[dict],
        prompt_hint: str = "",
    ) -> list[dict]:
        """
        Optionally enhance shot labels using VLM.

        Returns list of new label dicts (layer l3–l6, source cloud_vlm or local_vlm).
        Returns [] if disabled or provider unavailable.
        """
        ...
