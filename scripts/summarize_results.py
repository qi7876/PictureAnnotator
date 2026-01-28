from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Summarize per-image detection JSON results.")
    parser.add_argument(
        "--config",
        default=str(repo_root / "config" / "config.toml"),
        help="Path to config TOML (default: config/config.toml).",
    )
    args = parser.parse_args()
    config_path = Path(args.config).expanduser().resolve()

    # Best-effort: avoid hard dependency on the package for this stats script.
    try:
        import tomllib

        cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
        output_dir = Path(cfg.get("output", {}).get("dir", "output"))
    except Exception:
        output_dir = Path("output")

    output_root = (repo_root / output_dir).resolve()
    json_files = sorted(output_root.rglob("*.json"))

    if not json_files:
        print(f"No result json files found under: {output_root}")
        return

    counts: list[int] = []
    areas: list[float] = []
    for p in json_files:
        payload = json.loads(p.read_text(encoding="utf-8"))
        dets = payload.get("detections", [])
        counts.append(len(dets))
        w = float(payload.get("image", {}).get("width", 0))
        h = float(payload.get("image", {}).get("height", 0))
        img_area = max(w * h, 1.0)
        for det in dets:
            bbox = det.get("bbox", [0, 0, 0, 0])
            if not (isinstance(bbox, list) and len(bbox) == 4):
                continue
            xmin, ymin, xmax, ymax = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
            area = max((xmax - xmin), 0.0) * max((ymax - ymin), 0.0)
            areas.append(area / img_area)

    counts_sorted = sorted(counts)
    total = len(counts)
    print(f"Images: {total}")
    print(f"Total detections: {sum(counts)}")
    print(f"Detections/img: min={counts_sorted[0]} median={counts_sorted[total//2]} max={counts_sorted[-1]}")

    c = Counter(counts)
    common = ", ".join(f"{k}:{v}" for k, v in c.most_common(10))
    print(f"Top counts: {common}")

    if areas:
        areas_sorted = sorted(areas)
        n = len(areas_sorted)
        p50 = areas_sorted[n // 2]
        p90 = areas_sorted[int(n * 0.9)]
        p99 = areas_sorted[int(n * 0.99)]
        print(f"BBox area/image area: p50={p50:.6f} p90={p90:.6f} p99={p99:.6f}")


if __name__ == "__main__":
    main()
