from __future__ import annotations

import argparse
import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


def _display_width(text: str) -> int:
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in {"W", "F"} else 1
    return width


def _ljust(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _rjust(text: str, width: int) -> str:
    return " " * max(0, width - _display_width(text)) + text


def _is_returned(value: str) -> bool:
    v = value.strip().lower()
    return v in {"x", "√", "yes", "y", "1", "true", "是", "已发回"}


@dataclass(frozen=True, slots=True)
class PackageAssignment:
    package_id: int
    assignee: str
    returned: bool


@dataclass(slots=True)
class PersonStats:
    claimed_packages: list[int] = field(default_factory=list)
    returned_packages: list[int] = field(default_factory=list)
    unreturned_packages: list[int] = field(default_factory=list)

    claimed_photos: int = 0
    returned_photos: int = 0

    modified: int = 0
    deleted: int = 0
    added: int = 0

    missing_packages: list[int] = field(default_factory=list)
    missing_json_files: int = 0
    extra_json_files: int = 0
    json_parse_failures: int = 0

    @property
    def operated(self) -> int:
        return self.modified + self.deleted + self.added

    @property
    def claimed_package_count(self) -> int:
        return len(self.claimed_packages)

    @property
    def returned_package_count(self) -> int:
        return len(self.returned_packages)


def parse_support_md(path: Path) -> list[PackageAssignment]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()

    assignments: list[PackageAssignment] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if "压缩包id" in line.lower() and "领取人" in line:
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        try:
            package_id = int(parts[0])
        except ValueError:
            continue

        if len(parts) == 2:
            assignee = parts[1]
            returned = False
        else:
            returned = _is_returned(parts[-1])
            assignee = " ".join(parts[1:-1]).strip()
        if not assignee:
            assignee = "（未填写）"

        assignments.append(PackageAssignment(package_id=package_id, assignee=assignee, returned=returned))

    return assignments


def count_images(dataset_dir: Path) -> int:
    if not dataset_dir.exists():
        return 0
    return sum(
        1
        for p in dataset_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def _load_detection_map(path: Path) -> tuple[dict[int, tuple[float, float, float, float]], bool]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}, False

    dets = payload.get("detections", [])
    if not isinstance(dets, list):
        return {}, True

    mapping: dict[int, tuple[float, float, float, float]] = {}
    for det in dets:
        if not isinstance(det, dict):
            continue
        det_id = det.get("id")
        bbox = det.get("bbox")
        if not isinstance(det_id, int):
            continue
        if not (isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox)):
            continue
        mapping[det_id] = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))

    return mapping, True


def _bbox_changed(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    *,
    tol: float,
) -> bool:
    return any(abs(x - y) > tol for x, y in zip(a, b, strict=True))


def summarize_package(
    *,
    package_id: int,
    seg_pkg_dir: Path,
    result_pkg_dir: Path,
    tol: float,
    stats: PersonStats,
) -> None:
    orig_output_dir = seg_pkg_dir / "output"
    res_output_dir = result_pkg_dir / "output"

    if not orig_output_dir.exists() or not res_output_dir.exists():
        stats.missing_packages.append(package_id)
        return

    orig_rel_paths: set[str] = set()
    res_rel_paths: set[str] = set()

    for p in res_output_dir.rglob("*.json"):
        if p.is_file():
            res_rel_paths.add(p.relative_to(res_output_dir).as_posix())

    for orig_json in orig_output_dir.rglob("*.json"):
        if not orig_json.is_file():
            continue
        rel = orig_json.relative_to(orig_output_dir).as_posix()
        orig_rel_paths.add(rel)

        res_json = res_output_dir / rel
        if not res_json.exists():
            stats.missing_json_files += 1
            continue

        orig_map, ok1 = _load_detection_map(orig_json)
        res_map, ok2 = _load_detection_map(res_json)
        if not (ok1 and ok2):
            stats.json_parse_failures += 1
            continue

        orig_ids = set(orig_map)
        res_ids = set(res_map)

        stats.deleted += len(orig_ids - res_ids)
        stats.added += len(res_ids - orig_ids)

        for det_id in orig_ids & res_ids:
            if _bbox_changed(orig_map[det_id], res_map[det_id], tol=tol):
                stats.modified += 1

    stats.extra_json_files += len(res_rel_paths - orig_rel_paths)


def _render_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""

    col_count = max(len(r) for r in rows)
    widths = [0] * col_count
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], _display_width(cell))

    rendered: list[str] = []
    for idx, row in enumerate(rows):
        parts: list[str] = []
        for col_i, cell in enumerate(row):
            if col_i == 0:
                parts.append(_ljust(cell, widths[col_i]))
            else:
                parts.append(_rjust(cell, widths[col_i]))
        line = "  ".join(parts)
        rendered.append(line)

        if idx == 0:
            rendered.append("-" * _display_width(line))

    return "\n".join(rendered)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize outsource BBox correction workload.")
    parser.add_argument(
        "--post-data",
        default="post_data",
        help="Path to post_data directory (default: post_data).",
    )
    parser.add_argument(
        "--tol",
        type=float,
        default=1e-6,
        help="BBox change tolerance in pixels (default: 1e-6).",
    )
    args = parser.parse_args()

    post_root = Path(args.post_data).expanduser().resolve()
    support_md = post_root / "support.md"
    seg_root = post_root / "seg_data"
    result_root = post_root / "result"

    if not support_md.exists():
        raise FileNotFoundError(f"support.md not found: {support_md}")
    if not seg_root.exists():
        raise FileNotFoundError(f"seg_data not found: {seg_root}")
    if not result_root.exists():
        raise FileNotFoundError(f"result not found: {result_root}")

    assignments = parse_support_md(support_md)
    if not assignments:
        raise ValueError(f"No valid assignments found in: {support_md}")

    stats_by_person: dict[str, PersonStats] = {}
    for a in assignments:
        person_stats = stats_by_person.setdefault(a.assignee, PersonStats())
        seg_pkg = seg_root / f"data-{a.package_id}"
        res_pkg = result_root / f"data-{a.package_id}"

        person_stats.claimed_packages.append(a.package_id)

        if not seg_pkg.exists():
            person_stats.missing_packages.append(a.package_id)
            continue

        photo_count = count_images(seg_pkg / "dataset")
        person_stats.claimed_photos += photo_count

        if not a.returned:
            person_stats.unreturned_packages.append(a.package_id)
            continue

        person_stats.returned_packages.append(a.package_id)
        person_stats.returned_photos += photo_count
        summarize_package(
            package_id=a.package_id,
            seg_pkg_dir=seg_pkg,
            result_pkg_dir=res_pkg,
            tol=float(args.tol),
            stats=person_stats,
        )

    def sort_key(item: tuple[str, PersonStats]) -> tuple[int, int, int, str]:
        _name, st = item
        return (st.operated, st.returned_photos, st.returned_package_count, _name)

    sorted_people = sorted(stats_by_person.items(), key=sort_key, reverse=True)

    header = ["领取人", "领取包", "已发回包", "照片(领取)", "照片(已发回)", "修改框", "删除框", "新增框", "操作框合计"]
    rows: list[list[str]] = [header]

    total = PersonStats()
    for name, st in sorted_people:
        rows.append(
            [
                name,
                str(st.claimed_package_count),
                str(st.returned_package_count),
                str(st.claimed_photos),
                str(st.returned_photos),
                str(st.modified),
                str(st.deleted),
                str(st.added),
                str(st.operated),
            ]
        )

        total.claimed_packages.extend(st.claimed_packages)
        total.returned_packages.extend(st.returned_packages)
        total.unreturned_packages.extend(st.unreturned_packages)
        total.claimed_photos += st.claimed_photos
        total.returned_photos += st.returned_photos
        total.modified += st.modified
        total.deleted += st.deleted
        total.added += st.added
        total.missing_packages.extend(st.missing_packages)
        total.missing_json_files += st.missing_json_files
        total.extra_json_files += st.extra_json_files
        total.json_parse_failures += st.json_parse_failures

    rows.append(
        [
            "总计",
            str(total.claimed_package_count),
            str(total.returned_package_count),
            str(total.claimed_photos),
            str(total.returned_photos),
            str(total.modified),
            str(total.deleted),
            str(total.added),
            str(total.operated),
        ]
    )

    print(_render_table(rows))

    issues: list[str] = []
    if total.unreturned_packages:
        uniq = sorted(set(total.unreturned_packages))
        issues.append(f"- 未发回数据包：{', '.join(str(x) for x in uniq)}")
    if total.missing_packages:
        uniq = sorted(set(total.missing_packages))
        issues.append(f"- 缺少数据包目录：{', '.join(str(x) for x in uniq)}")
    if total.missing_json_files:
        issues.append(f"- 缺少结果 JSON：{total.missing_json_files} 个（按原始 output 逐一匹配）")
    if total.extra_json_files:
        issues.append(f"- 结果多余 JSON：{total.extra_json_files} 个（result 中存在但 seg_data 中不存在）")
    if total.json_parse_failures:
        issues.append(f"- JSON 解析失败：{total.json_parse_failures} 次（已跳过该文件统计）")

    if issues:
        print("\n注意：")
        print("\n".join(issues))


if __name__ == "__main__":
    main()
