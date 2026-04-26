#!/usr/bin/env python3
"""
Remove duplicate case snapshots when the newest scrape has no material changes.

Rule:
- Keep a new version only if canonical JSON changed vs previous kept version.
- If unchanged, delete the duplicate file and write a log entry.

Canonical comparison ignores volatile timestamp fields under metadata:
- scraped_at
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


RE_FILE = re.compile(r"^(\d{4})-(\d{6})_(\d{8}_\d{6})\.json$")


def canonicalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "metadata" and isinstance(v, dict):
                md = {mk: mv for mk, mv in v.items() if mk != "scraped_at"}
                out[k] = canonicalize(md)
            else:
                out[k] = canonicalize(v)
        return out
    if isinstance(obj, list):
        return [canonicalize(x) for x in obj]
    return obj


def digest(path: Path) -> str | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    can = canonicalize(obj)
    raw = json.dumps(can, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Compact duplicate case snapshots")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--log", default="logs/case_compaction.log")
    args = ap.parse_args()

    year_dir = Path(args.out_dir) / str(args.year)
    if not year_dir.exists():
        print(f"[compact] no directory: {year_dir}")
        return 0

    by_case: dict[str, list[Path]] = defaultdict(list)
    for p in year_dir.glob(f"{args.year}-*.json"):
        m = RE_FILE.match(p.name)
        if not m:
            continue
        case_num = m.group(2)
        by_case[case_num].append(p)

    removed = 0
    compared = 0
    kept = 0
    log_lines: list[str] = []

    for case_num, files in by_case.items():
        files.sort(key=lambda p: RE_FILE.match(p.name).group(3) if RE_FILE.match(p.name) else "")
        prev_hash = None
        prev_file = None

        for f in files:
            h = digest(f)
            if h is None:
                continue
            if prev_hash is None:
                prev_hash = h
                prev_file = f
                kept += 1
                continue

            compared += 1
            if h == prev_hash:
                removed += 1
                ts = datetime.now().isoformat(timespec="seconds")
                log_lines.append(
                    f"{ts} year={args.year} case={case_num} unchanged delete={f.name} keep={prev_file.name}"
                )
                if not args.dry_run:
                    try:
                        f.unlink()
                    except OSError:
                        pass
            else:
                prev_hash = h
                prev_file = f
                kept += 1

    print(f"[compact] year={args.year} compared={compared} removed={removed} kept={kept}")

    if log_lines and not args.dry_run:
        log_path = Path(args.log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(log_lines) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
