from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    parser = argparse.ArgumentParser(description="Run person detection (YOLO + SAHI).")
    parser.add_argument(
        "--config",
        default=str(repo_root / "config" / "config.toml"),
        help="Path to config TOML (default: config/config.toml).",
    )
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()

    from picture_annotator.config import load_config
    from picture_annotator.pipeline import run_pipeline

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config(config_path)
    run_pipeline(config=config, config_path=config_path)


if __name__ == "__main__":
    main()
