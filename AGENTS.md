# Repository Guidelines

## Project Structure & Module Organization

- `src/picture_annotator/`: core library (config loading, pipeline, detectors, output + visualization).
- `scripts/`: runnable entrypoints (`init_project.py`, `run_detection.py`, `summarize_results.py`).
- `config/`: TOML configs (`config.toml`, `config.example.toml`).
- `tests/`: pytest unit tests.
- `docs/`: reference docs (`CONFIG.md`, `OUTPUT_SCHEMA.md`, `TUNING.md`, `UV.md`).
- `data/`: local datasets/weights/output (ignored by git; do not commit).

Config paths in `config/*.toml` are resolved relative to the repo root (the directory containing
`pyproject.toml`).

## Build, Test, and Development Commands

This repo uses `uv` to manage the virtualenv and dependencies (`uv.lock` is checked in).

- `uv sync`: create/sync `.venv/` from `pyproject.toml` + `uv.lock`.
- `uv run python scripts/init_project.py`: create `data/dataset/`, `data/weights/`, `data/output/`, etc.
- `uv run python scripts/run_detection.py --config config/config.toml`: run detection on `data/dataset/`.
- `uv run python scripts/summarize_results.py --config config/config.toml`: summarize results for tuning.
- `uv run pytest`: run unit tests.
- `uv run ruff check .`: lint; `uv run ruff format .`: auto-format.

## Coding Style & Naming Conventions

- Python `>=3.11` (see `pyproject.toml`), 4-space indentation.
- Prefer `pathlib.Path`, type hints, and `from __future__ import annotations`.
- Keep lines ~100 chars (Ruff config); let Ruff manage imports (`I` rules).

## Testing Guidelines

- Framework: pytest (`tests/`, `test_*.py`).
- Add/extend tests when changing config parsing, path resolution, or output schema generation.

## Commit & Pull Request Guidelines

- Commits use short imperative messages (examples in history: `Add ...`, `Bootstrap ...`).
- PRs should include: problem/solution summary, config changes (if any), and a small before/after artifact
  (e.g., a JSON snippet from `data/output/` or an image from `data/visual_output/`).
- Never include large artifacts under `data/` (datasets, weights, generated outputs).

## Agent Notes (Optional)

- Keep changes focused; update docs in `docs/` when you change config or schema behavior.
- Before finalizing, run `uv run ruff check .` and `uv run pytest` when feasible.
