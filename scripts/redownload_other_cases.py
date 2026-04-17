#!/usr/bin/env python3
"""Build and optionally execute re-scrape batches for cases currently classified as OTHER.

By default this script prints planned commands only (dry run).
Use --execute to run the generated scrape commands.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from query_jobs import build_latest_dataset


def consecutive_ranges(nums: List[int]) -> List[Tuple[int, int]]:
    if not nums:
        return []
    nums = sorted(set(nums))
    ranges: List[Tuple[int, int]] = []
    start = nums[0]
    prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        ranges.append((start, prev))
        start = n
        prev = n
    ranges.append((start, prev))
    return ranges


def build_commands(
    by_year: Dict[int, List[int]],
    delay_ms: int,
    include_pdfs: bool,
) -> List[List[str]]:
    commands: List[List[str]] = []
    for year in sorted(by_year.keys()):
        ranges = consecutive_ranges(by_year[year])
        for start, end in ranges:
            limit = end - start + 1
            cmd = [
                sys.executable,
                "main.py",
                "scrape",
                "--year",
                str(year),
                "--start",
                str(start),
                "--limit",
                str(limit),
                "--direction",
                "up",
                "--delay-ms",
                str(delay_ms),
            ]
            if include_pdfs:
                cmd.extend(["--download-pdfs", "--all-pdfs"])
            commands.append(cmd)
    return commands


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-download cases currently labeled OTHER")
    ap.add_argument("--year", type=int, action="append", default=[], help="Filter year(s), can be repeated")
    ap.add_argument("--max-cases", type=int, default=0, help="Limit total case count (0 = no limit)")
    ap.add_argument("--delay-ms", type=int, default=1250, help="Delay for scrape commands")
    ap.add_argument("--include-pdfs", action="store_true", help="Also download all PDFs during re-scrape")
    ap.add_argument("--execute", action="store_true", help="Execute generated commands")
    args = ap.parse_args()

    df = build_latest_dataset()
    work = df[df["primary_crime_type"].eq("OTHER") & df["exists"].eq(True)].copy()

    if args.year:
        work = work[work["year"].isin(args.year)]

    if args.max_cases and args.max_cases > 0:
        work = work.sort_values(["year", "number"]).head(args.max_cases)

    if work.empty:
        print("No OTHER cases matched filters.")
        return 0

    by_year: Dict[int, List[int]] = {}
    for year, group in work.groupby("year"):
        by_year[int(year)] = sorted(group["number"].astype(int).tolist())

    commands = build_commands(by_year, delay_ms=args.delay_ms, include_pdfs=args.include_pdfs)

    print("Planned re-scrape scope:")
    print(f"  cases: {len(work)}")
    print(f"  years: {', '.join(str(y) for y in sorted(by_year.keys()))}")
    print(f"  command batches: {len(commands)}")
    print()

    preview_n = min(10, len(commands))
    print(f"First {preview_n} command(s):")
    for cmd in commands[:preview_n]:
        print("  " + " ".join(cmd))

    if not args.execute:
        print("\nDry run only. Re-run with --execute to start re-download.")
        return 0

    repo_root = Path(__file__).resolve().parent.parent
    failures = 0
    for idx, cmd in enumerate(commands, 1):
        print(f"\n[{idx}/{len(commands)}] Running: {' '.join(cmd)}")
        rc = subprocess.call(cmd, cwd=str(repo_root))
        if rc != 0:
            failures += 1
            print(f"  -> command failed with exit code {rc}")

    if failures:
        print(f"\nCompleted with {failures} failed batch(es).")
        return 1

    print("\nCompleted all re-scrape batches successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
