from __future__ import annotations

import json
from pathlib import Path

from picture_annotator.detectors.base import Detection
from picture_annotator.output import write_per_image_json


def test_write_per_image_json(tmp_path: Path) -> None:
    out_path = tmp_path / "x.json"
    detections = [
        Detection(id=0, bbox=(1.0, 2.0, 3.0, 4.0), score=0.9),
        Detection(id=1, bbox=(10.0, 20.0, 30.0, 40.0), score=0.1),
    ]
    write_per_image_json(
        output_path=out_path,
        file_name="x.png",
        relative_path="x.png",
        width=100,
        height=200,
        detections=detections,
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["format_version"] == "1.0"
    assert payload["image"]["file_name"] == "x.png"
    assert payload["image"]["width"] == 100
    assert len(payload["detections"]) == 2
    assert payload["detections"][0]["id"] == 0
    assert payload["detections"][0]["bbox"] == [1.0, 2.0, 3.0, 4.0]

