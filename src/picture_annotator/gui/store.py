from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from picture_annotator.config import AppConfig
from picture_annotator.image_utils import get_image_size
from picture_annotator.paths import iter_image_files, map_output_path
from picture_annotator.project import resolve_from


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


@dataclass(frozen=True, slots=True)
class ImageEntry:
    image_path: Path
    relative_path: str
    json_path: Path


@dataclass(slots=True)
class LoadReport:
    created_new_json: bool = False
    json_parse_failed: bool = False
    dropped_invalid: list[int] = field(default_factory=list)
    clamped_count: int = 0


@dataclass(slots=True)
class AnnotationSession:
    entry: ImageEntry
    width: int
    height: int
    payload: dict[str, Any]
    detections: list[dict[str, Any]]
    next_id: int
    dirty: bool = False


class AnnotationStore:
    def __init__(self, *, app_root: Path, config: AppConfig) -> None:
        self.app_root = app_root
        self.config = config

        self.input_dir = resolve_from(app_root, config.input.dir)
        self.output_dir = resolve_from(app_root, config.output.dir)

    def list_images(self) -> list[ImageEntry]:
        images = iter_image_files(
            input_dir=self.input_dir,
            recursive=self.config.input.recursive,
            extensions=self.config.input.extensions,
        )
        entries: list[ImageEntry] = []
        for image_path in images:
            rel = image_path.relative_to(self.input_dir)
            rel_str = str(rel).replace("\\", "/")
            json_path = map_output_path(
                output_dir=self.output_dir,
                input_dir=self.input_dir,
                image_path=image_path,
                suffix=".json",
            )
            entries.append(ImageEntry(image_path=image_path, relative_path=rel_str, json_path=json_path))
        return entries

    def load(self, entry: ImageEntry) -> tuple[AnnotationSession, LoadReport]:
        w, h = get_image_size(entry.image_path)
        report = LoadReport()

        if not entry.json_path.exists():
            payload = self._new_payload(entry=entry, width=w, height=h)
            entry.json_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_json_atomic(entry.json_path, payload)
            report.created_new_json = True
        else:
            try:
                payload = json.loads(entry.json_path.read_text(encoding="utf-8"))
            except Exception:
                payload = self._new_payload(entry=entry, width=w, height=h)
                report.json_parse_failed = True

        detections_raw = payload.get("detections", [])
        if not isinstance(detections_raw, list):
            detections_raw = []

        detections: list[dict[str, Any]] = []
        for det in detections_raw:
            if not isinstance(det, dict):
                continue
            det_id = det.get("id")
            bbox = det.get("bbox")
            score = det.get("score")
            if not isinstance(det_id, int):
                continue
            if not (isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox)):
                report.dropped_invalid.append(det_id)
                continue
            if not isinstance(score, (int, float)):
                report.dropped_invalid.append(det_id)
                continue
            xmin, ymin, xmax, ymax = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
            if xmin >= xmax or ymin >= ymax:
                report.dropped_invalid.append(det_id)
                continue

            clamped = self._clamp_bbox((xmin, ymin, xmax, ymax), width=w, height=h)
            if clamped != (xmin, ymin, xmax, ymax):
                report.clamped_count += 1
                det["bbox"] = [clamped[0], clamped[1], clamped[2], clamped[3]]
            detections.append(det)

        if report.dropped_invalid or report.json_parse_failed:
            payload["detections"] = detections

        max_id = max((d.get("id", -1) for d in detections if isinstance(d.get("id"), int)), default=-1)

        session = AnnotationSession(
            entry=entry,
            width=w,
            height=h,
            payload=payload,
            detections=detections,
            next_id=int(max_id) + 1,
            dirty=bool(report.dropped_invalid or report.json_parse_failed or report.clamped_count),
        )
        return session, report

    def save(self, session: AnnotationSession) -> None:
        for det in session.detections:
            bbox = det.get("bbox")
            if not (isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox)):
                continue
            xmin, ymin, xmax, ymax = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
            clamped = self._clamp_bbox((xmin, ymin, xmax, ymax), width=session.width, height=session.height)
            if clamped != (xmin, ymin, xmax, ymax):
                det["bbox"] = [clamped[0], clamped[1], clamped[2], clamped[3]]

        session.payload["detections"] = session.detections

        session.entry.json_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(session.entry.json_path, session.payload)
        session.dirty = False

    def add_box(self, session: AnnotationSession, bbox: tuple[float, float, float, float]) -> dict[str, Any]:
        xmin, ymin, xmax, ymax = self._clamp_bbox(bbox, width=session.width, height=session.height)
        det = {"id": session.next_id, "bbox": [xmin, ymin, xmax, ymax], "score": 1.0}
        session.next_id += 1
        session.detections.append(det)
        session.dirty = True
        return det

    def delete_box(self, session: AnnotationSession, det: dict[str, Any]) -> None:
        try:
            session.detections.remove(det)
        except ValueError:
            return
        session.dirty = True

    def _new_payload(self, *, entry: ImageEntry, width: int, height: int) -> dict[str, Any]:
        return {
            "format_version": "1.0",
            "image": {
                "file_name": entry.image_path.name,
                "relative_path": entry.relative_path,
                "width": int(width),
                "height": int(height),
            },
            "detections": [],
        }

    def _clamp_bbox(
        self, bbox: tuple[float, float, float, float], *, width: int, height: int
    ) -> tuple[float, float, float, float]:
        xmin, ymin, xmax, ymax = bbox

        w = float(width)
        h = float(height)

        xmin = _clamp(float(xmin), 0.0, max(w - 1.0, 0.0))
        ymin = _clamp(float(ymin), 0.0, max(h - 1.0, 0.0))
        xmax = _clamp(float(xmax), min(1.0, w), w)
        ymax = _clamp(float(ymax), min(1.0, h), h)

        if xmax - xmin < 1.0:
            xmax = min(w, xmin + 1.0)
            xmin = max(0.0, xmax - 1.0)
        if ymax - ymin < 1.0:
            ymax = min(h, ymin + 1.0)
            ymin = max(0.0, ymax - 1.0)

        return (xmin, ymin, xmax, ymax)

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
