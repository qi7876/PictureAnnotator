from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from picture_annotator.config import AppConfig
from picture_annotator.detectors.base import Detection

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _SahiRuntime:
    detection_model: Any
    get_sliced_prediction: Any


class YoloSahiPersonDetector:
    def __init__(self, *, config: AppConfig, project_root: Path) -> None:
        self._config = config
        self._project_root = project_root
        self._sahi: _SahiRuntime | None = None
        self._ultralytics_model: Any | None = None

    def detect(self, image_path: Path) -> list[Detection]:
        if self._config.sahi.enabled:
            return self._detect_with_sahi(image_path)
        return self._detect_full_image(image_path)

    def _resolve_weights_arg(self) -> str:
        weights = self._config.model.weights.strip()
        if not weights:
            raise ValueError("config: model.weights must be a non-empty string")

        # URL weights are passed through as-is.
        if "://" in weights:
            return weights

        weights_path = self._resolve_weights_path(weights)
        weights_path = self._ensure_weights_available(weights_path)
        return str(weights_path)

    def _resolve_weights_path(self, weights: str) -> Path:
        """
        Resolves `model.weights` to an absolute local file path.

        Rules:
        - absolute path: use as-is
        - relative path (contains '/' or '\\' or starts with '.'): relative to project root
        - bare asset name (e.g. yolov8m.pt): stored under data/weights/
        """
        weights_path = Path(weights)
        if weights_path.is_absolute():
            resolved = weights_path
        elif any(sep in weights for sep in ("/", "\\")) or weights.startswith("."):
            resolved = (self._project_root / weights_path).resolve()
        else:
            resolved = (self._project_root / "data" / "weights" / weights_path).resolve()

        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def _ensure_weights_available(self, weights_path: Path) -> Path:
        """
        Best-effort download for known Ultralytics assets when weights are missing.
        """
        if weights_path.exists():
            return weights_path

        try:
            from ultralytics.utils.downloads import (
                attempt_download_asset,  # type: ignore[import-not-found]
            )
        except ModuleNotFoundError:
            attempt_download_asset = None  # type: ignore[assignment]

        if attempt_download_asset is not None:
            attempt_download_asset(weights_path)

        if not weights_path.exists():
            raise FileNotFoundError(
                "Weights file not found. Set `model.weights` to a valid local `.pt` path, "
                f"or use a known Ultralytics asset name. Path: {weights_path}"
            )

        return weights_path

    def _ensure_sahi(self) -> _SahiRuntime:
        if self._sahi is not None:
            return self._sahi

        try:
            from sahi import AutoDetectionModel  # type: ignore[import-not-found]
            from sahi.predict import get_sliced_prediction  # type: ignore[import-not-found]
        except ModuleNotFoundError as e:  # pragma: no cover
            raise RuntimeError(
                "Missing dependency: sahi. Install with `uv sync` (see README)."
            ) from e

        weights = self._resolve_weights_arg()

        last_error: Exception | None = None
        for model_type in ("yolov8", "ultralytics"):
            try:
                detection_model = AutoDetectionModel.from_pretrained(
                    model_type=model_type,
                    model_path=weights,
                    confidence_threshold=self._config.model.confidence_threshold,
                    device=self._config.model.device,
                    image_size=self._config.model.imgsz,
                )
                LOGGER.info("SAHI model_type=%s weights=%s", model_type, weights)
                self._sahi = _SahiRuntime(
                    detection_model=detection_model,
                    get_sliced_prediction=get_sliced_prediction,
                )
                return self._sahi
            except Exception as e:  # pragma: no cover
                last_error = e

        raise RuntimeError(
            "Failed to initialize SAHI AutoDetectionModel "
            f"(weights={weights}). Last error: {last_error}"
        )

    def _detect_with_sahi(self, image_path: Path) -> list[Detection]:
        sahi_rt = self._ensure_sahi()

        result = sahi_rt.get_sliced_prediction(
            str(image_path),
            sahi_rt.detection_model,
            slice_height=self._config.sahi.slice_height,
            slice_width=self._config.sahi.slice_width,
            overlap_height_ratio=self._config.sahi.overlap_height_ratio,
            overlap_width_ratio=self._config.sahi.overlap_width_ratio,
            postprocess_type=self._config.sahi.postprocess_type,
            postprocess_match_metric=self._config.sahi.postprocess_match_metric,
            postprocess_match_threshold=self._config.sahi.postprocess_match_threshold,
        )

        try:
            preds = result.object_prediction_list
        except AttributeError as e:
            raise RuntimeError(
                "SAHI returned unexpected prediction result: missing object_prediction_list"
            ) from e
        if preds is None:
            raise RuntimeError("SAHI returned unexpected prediction result: object_prediction_list is None")

        detections: list[tuple[tuple[float, float, float, float], float]] = []
        for pred in preds:
            if not _is_person_prediction(pred):
                continue
            try:
                bbox = pred.bbox
            except AttributeError:
                continue
            if bbox is None:
                continue

            try:
                minx = float(bbox.minx)
                miny = float(bbox.miny)
                maxx = float(bbox.maxx)
                maxy = float(bbox.maxy)
            except AttributeError:
                continue

            score = 0.0
            try:
                score_attr = pred.score
                try:
                    score = float(score_attr.value)
                except Exception:
                    score = float(score_attr)
            except Exception:
                score = 0.0

            detections.append(((minx, miny, maxx, maxy), score))

        detections.sort(key=lambda x: x[1], reverse=True)
        return [
            Detection(id=i, bbox=bbox, score=score)
            for i, (bbox, score) in enumerate(detections[: self._config.model.max_det])
        ]

    def _ensure_ultralytics_model(self) -> Any:
        if self._ultralytics_model is not None:
            return self._ultralytics_model

        try:
            from ultralytics import YOLO  # type: ignore[import-not-found]
        except ModuleNotFoundError as e:  # pragma: no cover
            raise RuntimeError(
                "Missing dependency: ultralytics. Install with `uv sync` (see README)."
            ) from e

        weights = self._resolve_weights_arg()
        self._ultralytics_model = YOLO(weights)
        return self._ultralytics_model

    def _detect_full_image(self, image_path: Path) -> list[Detection]:
        model = self._ensure_ultralytics_model()

        results = model.predict(
            source=str(image_path),
            conf=self._config.model.confidence_threshold,
            iou=self._config.model.iou_threshold,
            device=self._config.model.device,
            imgsz=self._config.model.imgsz,
            max_det=self._config.model.max_det,
            verbose=False,
        )

        if not results:
            return []

        # Ultralytics result parsing (YOLOv8+)
        result0 = results[0]
        boxes = getattr(result0, "boxes", None)
        if boxes is None:
            return []

        xyxy = getattr(boxes, "xyxy", None)
        conf = getattr(boxes, "conf", None)
        cls = getattr(boxes, "cls", None)
        if xyxy is None or conf is None or cls is None:
            return []

        detections: list[tuple[tuple[float, float, float, float], float]] = []
        for coords, score, class_id in zip(xyxy.tolist(), conf.tolist(), cls.tolist(), strict=False):
            if int(class_id) != 0:
                continue
            minx, miny, maxx, maxy = (float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3]))
            detections.append(((minx, miny, maxx, maxy), float(score)))

        detections.sort(key=lambda x: x[1], reverse=True)
        return [Detection(id=i, bbox=bbox, score=score) for i, (bbox, score) in enumerate(detections)]


def _is_person_prediction(pred: Any) -> bool:
    category = getattr(pred, "category", None)
    if category is None:
        return False

    name = getattr(category, "name", None)
    if isinstance(name, str) and name.lower() == "person":
        return True

    category_id = getattr(category, "id", None)
    if category_id is None:
        return False
    try:
        return int(category_id) == 0
    except (TypeError, ValueError):
        return False
