from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_dir(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise NotADirectoryError(f"Expected a directory but found a file: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _resolve_weights_dir(*, project_root: Path, weights: str) -> Path | None:
    weights = weights.strip()
    if not weights:
        return None
    if "://" in weights:
        return None

    weights_path = Path(weights)
    if weights_path.is_absolute():
        return weights_path.parent

    if any(sep in weights for sep in ("/", "\\")) or weights.startswith("."):
        return (project_root / weights_path).resolve().parent

    # Bare name like "yolov8x.pt" -> keep under data/weights/
    return (project_root / "data" / "weights").resolve()


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    parser = argparse.ArgumentParser(
        description="Initialize the data directory structure based on config.",
    )
    parser.add_argument(
        "--config",
        default=str(repo_root / "config" / "config.toml"),
        help="Path to config TOML (default: config/config.toml).",
    )
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()

    from picture_annotator.config import load_config
    from picture_annotator.project import find_project_root, resolve_from

    config = load_config(config_path)
    project_root = find_project_root(config_path)

    input_dir = resolve_from(project_root, config.input.dir)
    output_dir = resolve_from(project_root, config.output.dir)
    vis_dir = resolve_from(project_root, config.visualization.dir)
    weights_dir = _resolve_weights_dir(project_root=project_root, weights=config.model.weights)

    dirs = [input_dir, output_dir, vis_dir]
    if weights_dir is not None:
        dirs.append(weights_dir)

    for d in dirs:
        _ensure_dir(d)

    print("Initialized directories:")
    for d in dirs:
        print(f"- {d}")


if __name__ == "__main__":
    main()

