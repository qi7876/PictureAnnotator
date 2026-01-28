from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from picture_annotator.detectors.base import Detection


def write_per_image_json(
    *,
    output_path: Path,
    file_name: str,
    relative_path: str,
    width: int,
    height: int,
    detections: list[Detection],
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "format_version": "1.0",
        "image": {
            "file_name": file_name,
            "relative_path": relative_path,
            "width": int(width),
            "height": int(height),
        },
        "detections": [
            {"id": det.id, "bbox": list(det.bbox), "score": float(det.score)} for det in detections
        ],
    }

    if extra:
        payload["extra"] = extra

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _debug_detection(det: Detection) -> dict[str, Any]:
    return asdict(det)

