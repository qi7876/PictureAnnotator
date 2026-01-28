from __future__ import annotations

import logging
from pathlib import Path

from picture_annotator.config import AppConfig
from picture_annotator.detectors.yolo_sahi import YoloSahiPersonDetector
from picture_annotator.image_utils import get_image_size
from picture_annotator.output import write_per_image_json
from picture_annotator.paths import iter_image_files, map_output_path
from picture_annotator.project import find_project_root, resolve_from
from picture_annotator.visualize import save_visualization

LOGGER = logging.getLogger(__name__)


def run_pipeline(*, config: AppConfig, config_path: Path) -> None:
    project_root = find_project_root(config_path)

    input_dir = resolve_from(project_root, config.input.dir)
    output_dir = resolve_from(project_root, config.output.dir)
    vis_dir = resolve_from(project_root, config.visualization.dir)

    if not input_dir.exists():
        raise FileNotFoundError(f"input.dir not found: {input_dir}")

    images = iter_image_files(
        input_dir=input_dir,
        recursive=config.input.recursive,
        extensions=config.input.extensions,
    )
    LOGGER.info("Found %d images under %s", len(images), input_dir)

    detector = YoloSahiPersonDetector(config=config, project_root=project_root)

    try:
        from tqdm import tqdm  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        tqdm = None  # type: ignore[assignment]

    iterator = tqdm(images, desc="detect") if tqdm else images

    for image_path in iterator:
        rel = image_path.relative_to(input_dir)
        out_json_path = map_output_path(
            output_dir=output_dir,
            input_dir=input_dir,
            image_path=image_path,
            suffix=".json",
        )
        out_vis_path = map_output_path(
            output_dir=vis_dir,
            input_dir=input_dir,
            image_path=image_path,
            suffix=".png",
        )

        if out_json_path.exists() and not config.output.overwrite:
            continue

        detections = detector.detect(image_path)
        w, h = get_image_size(image_path)

        if (not detections) and (not config.output.write_empty):
            continue

        write_per_image_json(
            output_path=out_json_path,
            file_name=image_path.name,
            relative_path=str(rel).replace("\\", "/"),
            width=w,
            height=h,
            detections=detections,
        )

        if config.visualization.enabled:
            save_visualization(
                image_path=image_path,
                detections=detections,
                output_path=out_vis_path,
                config=config,
            )
