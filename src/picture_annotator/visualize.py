from __future__ import annotations

from pathlib import Path

from picture_annotator.config import AppConfig
from picture_annotator.detectors.base import Detection


def save_visualization(
    *, image_path: Path, detections: list[Detection], output_path: Path, config: AppConfig
) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-not-found]
    except ModuleNotFoundError as e:  # pragma: no cover
        raise RuntimeError(
            "Visualization requires Pillow. Install with `uv sync` (see README)."
        ) from e

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as im:
        im = im.convert("RGB")
        draw = ImageDraw.Draw(im)
        font = ImageFont.load_default()

        color = tuple(config.visualization.box_color)
        width = int(config.visualization.line_width)

        for det in detections:
            xmin, ymin, xmax, ymax = det.bbox
            draw.rectangle([xmin, ymin, xmax, ymax], outline=color, width=width)
            if config.visualization.write_label:
                label = f"{det.id}:{det.score:.2f}"
                draw.text((xmin + 2, ymin + 2), label, fill=color, font=font)

        im.save(output_path)

