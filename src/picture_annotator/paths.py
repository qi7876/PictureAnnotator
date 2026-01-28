from __future__ import annotations

from pathlib import Path


def iter_image_files(*, input_dir: Path, recursive: bool, extensions: tuple[str, ...]) -> list[Path]:
    exts = tuple(x.lower() for x in extensions)
    if recursive:
        candidates = input_dir.rglob("*")
    else:
        candidates = input_dir.glob("*")

    images: list[Path] = []
    for p in candidates:
        if not p.is_file():
            continue
        if p.suffix.lower() in exts:
            images.append(p)

    images.sort()
    return images


def map_output_path(*, output_dir: Path, input_dir: Path, image_path: Path, suffix: str) -> Path:
    rel = image_path.relative_to(input_dir)
    return (output_dir / rel).with_suffix(suffix)

