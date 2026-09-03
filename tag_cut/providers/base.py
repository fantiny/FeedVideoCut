"""Base provider protocols for tag_cut."""
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class VisionProvider(Protocol):
    def detect(self, image_path: Path) -> list[dict]: ...
