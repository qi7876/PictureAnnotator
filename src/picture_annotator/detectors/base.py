from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Detection:
    id: int
    bbox: tuple[float, float, float, float]  # xmin, ymin, xmax, ymax (pixels)
    score: float


class PersonDetector(Protocol):
    def detect(self, image_path: Path) -> list[Detection]:
        ...

