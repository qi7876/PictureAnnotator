from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_INPUT_EXTENSIONS: tuple[str, ...] = (".png", ".jpg", ".jpeg")
DEFAULT_VIS_BOX_COLOR: tuple[int, int, int] = (0, 255, 0)


@dataclass(frozen=True, slots=True)
class InputConfig:
    dir: Path
    recursive: bool = False
    extensions: tuple[str, ...] = DEFAULT_INPUT_EXTENSIONS


@dataclass(frozen=True, slots=True)
class OutputConfig:
    dir: Path
    overwrite: bool = True
    write_empty: bool = True


@dataclass(frozen=True, slots=True)
class VisualizationConfig:
    enabled: bool = True
    dir: Path = Path("data/visual_output")
    box_color: tuple[int, int, int] = DEFAULT_VIS_BOX_COLOR
    line_width: int = 2
    write_label: bool = True


@dataclass(frozen=True, slots=True)
class ModelConfig:
    weights: str = "data/weights/yolov8x.pt"
    device: str = "cpu"
    confidence_threshold: float = 0.1
    iou_threshold: float = 0.5
    imgsz: int = 1280
    max_det: int = 300


@dataclass(frozen=True, slots=True)
class SahiConfig:
    enabled: bool = True
    slice_height: int = 640
    slice_width: int = 640
    overlap_height_ratio: float = 0.2
    overlap_width_ratio: float = 0.2
    postprocess_type: str = "NMS"
    postprocess_match_metric: str = "IOU"
    postprocess_match_threshold: float = 0.5


@dataclass(frozen=True, slots=True)
class AppConfig:
    input: InputConfig
    output: OutputConfig
    visualization: VisualizationConfig
    model: ModelConfig
    sahi: SahiConfig


def _as_dict_table(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"config: [{name}] must be a TOML table")
    return value


def _require_path(value: Any, name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"config: {name} must be a non-empty string path")
    return Path(value)


def _get_bool(table: dict[str, Any], key: str, default: bool) -> bool:
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise TypeError(f"config: {key} must be a bool")
    return value


def _get_int(table: dict[str, Any], key: str, default: int) -> int:
    value = table.get(key, default)
    if not isinstance(value, int):
        raise TypeError(f"config: {key} must be an int")
    return value


def _get_float(table: dict[str, Any], key: str, default: float) -> float:
    value = table.get(key, default)
    if not isinstance(value, (int, float)):
        raise TypeError(f"config: {key} must be a number")
    return float(value)


def _get_str(table: dict[str, Any], key: str, default: str) -> str:
    value = table.get(key, default)
    if not isinstance(value, str):
        raise TypeError(f"config: {key} must be a string")
    return value


def _get_str_list(table: dict[str, Any], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = table.get(key)
    if value is None:
        return default
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise TypeError(f"config: {key} must be a list of strings")
    return tuple(value)


def _get_rgb(table: dict[str, Any], key: str, default: tuple[int, int, int]) -> tuple[int, int, int]:
    value = table.get(key)
    if value is None:
        return default
    if (
        not isinstance(value, list)
        or len(value) != 3
        or not all(isinstance(x, int) for x in value)
        or not all(0 <= x <= 255 for x in value)
    ):
        raise TypeError(f"config: {key} must be [r,g,b] ints in 0..255")
    return (value[0], value[1], value[2])


def _validate(config: AppConfig) -> None:
    if config.model.imgsz <= 0:
        raise ValueError("config: model.imgsz must be > 0")
    if config.model.max_det <= 0:
        raise ValueError("config: model.max_det must be > 0")
    if not (0.0 <= config.model.confidence_threshold <= 1.0):
        raise ValueError("config: model.confidence_threshold must be in [0,1]")
    if not (0.0 <= config.model.iou_threshold <= 1.0):
        raise ValueError("config: model.iou_threshold must be in [0,1]")
    if config.sahi.slice_height <= 0 or config.sahi.slice_width <= 0:
        raise ValueError("config: sahi.slice_height/slice_width must be > 0")
    if not (0.0 <= config.sahi.overlap_height_ratio < 1.0):
        raise ValueError("config: sahi.overlap_height_ratio must be in [0,1)")
    if not (0.0 <= config.sahi.overlap_width_ratio < 1.0):
        raise ValueError("config: sahi.overlap_width_ratio must be in [0,1)")
    if config.visualization.line_width <= 0:
        raise ValueError("config: visualization.line_width must be > 0")


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")

    import tomllib

    data = tomllib.loads(path.read_text(encoding="utf-8"))

    input_table = _as_dict_table(data.get("input"), "input")
    output_table = _as_dict_table(data.get("output"), "output")
    vis_table = _as_dict_table(data.get("visualization"), "visualization")
    model_table = _as_dict_table(data.get("model"), "model")
    sahi_table = _as_dict_table(data.get("sahi"), "sahi")

    config = AppConfig(
        input=InputConfig(
            dir=_require_path(input_table.get("dir", "data/dataset"), "input.dir"),
            recursive=_get_bool(input_table, "recursive", False),
            extensions=_get_str_list(input_table, "extensions", DEFAULT_INPUT_EXTENSIONS),
        ),
        output=OutputConfig(
            dir=_require_path(output_table.get("dir", "data/output"), "output.dir"),
            overwrite=_get_bool(output_table, "overwrite", True),
            write_empty=_get_bool(output_table, "write_empty", True),
        ),
        visualization=VisualizationConfig(
            enabled=_get_bool(vis_table, "enabled", True),
            dir=_require_path(vis_table.get("dir", "data/visual_output"), "visualization.dir"),
            box_color=_get_rgb(vis_table, "box_color", DEFAULT_VIS_BOX_COLOR),
            line_width=_get_int(vis_table, "line_width", 2),
            write_label=_get_bool(vis_table, "write_label", True),
        ),
        model=ModelConfig(
            weights=_get_str(model_table, "weights", "data/weights/yolov8x.pt"),
            device=_get_str(model_table, "device", "cpu"),
            confidence_threshold=_get_float(
                model_table, "confidence_threshold", 0.1
            ),
            iou_threshold=_get_float(model_table, "iou_threshold", 0.5),
            imgsz=_get_int(model_table, "imgsz", 1280),
            max_det=_get_int(model_table, "max_det", 300),
        ),
        sahi=SahiConfig(
            enabled=_get_bool(sahi_table, "enabled", True),
            slice_height=_get_int(sahi_table, "slice_height", 640),
            slice_width=_get_int(sahi_table, "slice_width", 640),
            overlap_height_ratio=_get_float(
                sahi_table, "overlap_height_ratio", 0.2
            ),
            overlap_width_ratio=_get_float(
                sahi_table, "overlap_width_ratio", 0.2
            ),
            postprocess_type=_get_str(sahi_table, "postprocess_type", "NMS"),
            postprocess_match_metric=_get_str(
                sahi_table, "postprocess_match_metric", "IOU"
            ),
            postprocess_match_threshold=_get_float(
                sahi_table, "postprocess_match_threshold", 0.5
            ),
        ),
    )

    _validate(config)
    return config
