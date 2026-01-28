from __future__ import annotations

from pathlib import Path

from picture_annotator.paths import iter_image_files, map_output_path


def test_iter_image_files(tmp_path: Path) -> None:
    (tmp_path / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "b.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "c.txt").write_text("x", encoding="utf-8")

    images = iter_image_files(input_dir=tmp_path, recursive=False, extensions=(".png", ".jpg"))
    assert [p.name for p in images] == ["a.png", "b.jpg"]


def test_map_output_path(tmp_path: Path) -> None:
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    image_path = input_dir / "sub" / "x.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_text("x", encoding="utf-8")

    out = map_output_path(output_dir=output_dir, input_dir=input_dir, image_path=image_path, suffix=".json")
    assert out == output_dir / "sub" / "x.json"

