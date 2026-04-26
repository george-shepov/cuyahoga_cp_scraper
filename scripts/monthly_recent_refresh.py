#!/usr/bin/env python3
"""
Monthly refresh for recent county filings + Brockler cases.

- Re-scrapes recent cases (default 90 days by file timestamp) for change detection.
- Always includes Brockler attorney-of-record cases.
- Downloads PDFs for each refreshed case.
- Runs compaction to avoid duplicate unchanged snapshots.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "out"
RE_FILE = re.compile(r"^(\d{4})-(\d{6})_(\d{8}_\d{6})\.json$")
BROCKLER_KEYS = ("BROCKLER", "AARON BROCKLER", "BROCKLER LAW")


def parse_ts_from_name(name: str) -> datetime | None:
    m = RE_FILE.match(name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(3), "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def latest_files_by_case(year: int) -> dict[int, Path]:
    year_dir = OUT_ROOT / str(year)
    out: dict[int, tuple[str, Path]] = {}
    if not year_dir.exists():
        return {}
    for p in year_dir.glob(f"{year}-*.json"):
        m = RE_FILE.match(p.name)
        if not m:
            continue
        num = int(m.group(2))
        ts = m.group(3)
        prev = out.get(num)
        if prev is None or ts > prev[0]:
            out[num] = (ts, p)
    return {k: v[1] for k, v in out.items()}


def is_brockler_case(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    attys = data.get("attorneys") or []
    for a in attys:
        name = str((a or {}).get("name", "")).upper()
        party = str((a or {}).get("party", "")).upper()
        if party == "DEFENSE" and any(k in name for k in BROCKLER_KEYS):
            return True
    return False


def run_cmd(cmd: list[str]) -> int:
    print("[monthly] RUN:", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Monthly refresh for recent + Brockler cases")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--year", type=int, default=datetime.now().year)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--delay-ms", type=int, default=1000)
    ap.add_argument("--max-cases", type=int, default=250)
    ap.add_argument("--download-pdfs", action="store_true")
    args = ap.parse_args()

    years = sorted({args.year, args.year - 1})
    cutoff = datetime.now() - timedelta(days=args.days)
    targets: dict[int, set[int]] = defaultdict(set)

    for y in years:
        latest = latest_files_by_case(y)
        for num, p in latest.items():
            ts = parse_ts_from_name(p.name)
            if ts and ts >= cutoff:
                targets[y].add(num)
            if is_brockler_case(p):
                targets[y].add(num)

    total = sum(len(v) for v in targets.values())
    if total == 0:
        print("[monthly] no target cases found")
        return 0

    print(f"[monthly] target cases={total} across years={sorted(targets.keys())}")

    processed = 0
    for y in sorted(targets.keys()):
        for num in sorted(targets[y]):
            if processed >= args.max_cases:
                break
            cmd = [
                sys.executable,
                "main.py",
                "scrape",
                "--year",
                str(y),
                "--start",
                str(num),
                "--limit",
                "1",
                "--direction",
                "up",
                "--delay-ms",
                str(args.delay_ms),
            ]
            if args.headless:
                cmd.append("--headless")
            if args.download_pdfs:
                cmd.append("--download-pdfs")
                cmd.append("--all-pdfs")

            rc = run_cmd(cmd)
            if rc != 0:
                print(f"[monthly] warning scrape failed year={y} num={num} rc={rc}")
            processed += 1

        # compact each touched year to avoid unchanged duplicates
        rc = run_cmd([sys.executable, "scripts/compact_case_versions.py", "--year", str(y)])
        if rc != 0:
            print(f"[monthly] compaction failed for year={y}")

    print(f"[monthly] processed={processed} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
