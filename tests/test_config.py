from __future__ import annotations

from pathlib import Path

import pytest

from picture_annotator.config import load_config


def test_load_config_minimal(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[input]
dir = "data"

[output]
dir = "out"

[visualization]
enabled = false
dir = "vis"

[model]
weights = "yolov8m.pt"
device = "cpu"

[sahi]
enabled = true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = load_config(config_path)
    assert cfg.input.dir == Path("data")
    assert cfg.output.dir == Path("out")
    assert cfg.visualization.enabled is False
    assert cfg.sahi.enabled is True


def test_load_config_invalid_overlap(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[input]
dir = "data"

[output]
dir = "out"

[visualization]
enabled = false
dir = "vis"

[model]
weights = "yolov8m.pt"
device = "cpu"

[sahi]
enabled = true
overlap_width_ratio = 1.2
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_config(config_path)

