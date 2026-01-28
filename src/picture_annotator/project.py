from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path) -> Path:
    """
    Walk upwards from `start` to find the project root (directory containing `pyproject.toml`).
    Falls back to `start.parent` if not found.
    """
    cursor = start.resolve()
    if cursor.is_file():
        cursor = cursor.parent

    for parent in (cursor, *cursor.parents):
        if (parent / "pyproject.toml").exists():
            return parent

    return start.resolve().parent if start.is_file() else start.resolve()


def resolve_from(base_dir: Path, maybe_relative: Path) -> Path:
    """
    Resolve `maybe_relative` against `base_dir` when it's not absolute.
    """
    if maybe_relative.is_absolute():
        return maybe_relative
    return (base_dir / maybe_relative).resolve()

