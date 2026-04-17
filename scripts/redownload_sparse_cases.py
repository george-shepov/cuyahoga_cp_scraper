#!/usr/bin/env python3
"""Identify low-specificity cases and re-download them in batched ranges.

A case is considered sparse if one or more key fields are missing or weak:
- empty defendant
- no defense attorneys
- empty docket
- no charges
- UNKNOWN/OTHER crime type
- UNKNOWN outcome bucket

Default mode is dry-run; use --execute to run generated scrape commands.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from query_jobs import build_latest_dataset


def consecutive_ranges(nums: List[int]) -> List[Tuple[int, int]]:
    if not nums:
        return []
    nums = sorted(set(nums))
    out: List[Tuple[int, int]] = []
    start = nums[0]
    prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        out.append((start, prev))
        start = n
        prev = n
    out.append((start, prev))
    return out


def build_reason_columns(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()

    work["missing_defendant"] = work["defendant"].astype(str).str.strip().eq("")
    work["missing_attorneys"] = work["attorneys"].astype(str).str.strip().eq("")
    work["missing_docket"] = pd.to_numeric(work["docket_count"], errors="coerce").fillna(0).eq(0)
    work["missing_charges"] = pd.to_numeric(work["charge_count"], errors="coerce").fillna(0).eq(0)
    work["weak_crime_type"] = work["primary_crime_type"].isin(["UNKNOWN", "OTHER"])
    work["unknown_outcome"] = work["outcome_bucket"].astype(str).eq("UNKNOWN")

    reason_cols = [
        "missing_defendant",
        "missing_attorneys",
        "missing_docket",
        "missing_charges",
        "weak_crime_type",
        "unknown_outcome",
    ]
    work["gap_score"] = work[reason_cols].sum(axis=1)

    def reasons(row: pd.Series) -> str:
        parts: List[str] = []
        for c in reason_cols:
            if bool(row.get(c, False)):
                parts.append(c)
        return ",".join(parts)

    work["gap_reasons"] = work.apply(reasons, axis=1)
    return work


def build_commands(by_year: Dict[int, List[int]], delay_ms: int, include_pdfs: bool) -> List[List[str]]:
    cmds: List[List[str]] = []
    for year in sorted(by_year.keys()):
        for start, end in consecutive_ranges(by_year[year]):
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
                "--workers",
                "1",
            ]
            if include_pdfs:
                cmd.extend(["--download-pdfs", "--all-pdfs"])
            cmds.append(cmd)
    return cmds


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-download sparse/incomplete case snapshots")
    ap.add_argument("--year", type=int, action="append", default=[], help="Filter year(s), repeatable")
    ap.add_argument("--min-gap-score", type=int, default=2, help="Minimum missing-field score to include")
    ap.add_argument("--max-cases", type=int, default=0, help="Limit case count to process (0 = no limit)")
    ap.add_argument("--delay-ms", type=int, default=1250, help="Delay for scrape commands")
    ap.add_argument("--include-pdfs", action="store_true", help="Also download all PDFs during re-scrape")
    ap.add_argument("--execute", action="store_true", help="Execute generated commands")
    args = ap.parse_args()

    df = build_latest_dataset()
    work = build_reason_columns(df)
    work = work[work["exists"].eq(True)]
    work = work[work["gap_score"] >= max(1, args.min_gap_score)]

    if args.year:
        work = work[work["year"].isin(args.year)]

    work = work.sort_values(["gap_score", "year", "number"], ascending=[False, True, True])

    if args.max_cases and args.max_cases > 0:
        work = work.head(args.max_cases)

    if work.empty:
        print("No sparse cases matched filters.")
        return 0

    by_year: Dict[int, List[int]] = {}
    for year, grp in work.groupby("year"):
        by_year[int(year)] = sorted(grp["number"].astype(int).tolist())

    cmds = build_commands(by_year, args.delay_ms, args.include_pdfs)

    print("Planned sparse-case re-download scope:")
    print(f"  cases: {len(work)}")
    print(f"  years: {', '.join(str(y) for y in sorted(by_year.keys()))}")
    print(f"  command batches: {len(cmds)}")
    print()

    print("Reason counts:")
    reason_cols = [
        "missing_defendant",
        "missing_attorneys",
        "missing_docket",
        "missing_charges",
        "weak_crime_type",
        "unknown_outcome",
    ]
    for c in reason_cols:
        print(f"  {c}: {int(work[c].sum())}")
    print()

    print("Top 20 sparse cases:")
    show = work[["year", "number", "gap_score", "gap_reasons", "file"]].head(20)
    for _, r in show.iterrows():
        print(f"  {int(r['year'])}-{int(r['number']):06d} score={int(r['gap_score'])} reasons={r['gap_reasons']}")

    print()
    preview_n = min(10, len(cmds))
    print(f"First {preview_n} command(s):")
    for c in cmds[:preview_n]:
        print("  " + " ".join(c))

    if not args.execute:
        print("\nDry run only. Re-run with --execute to start re-download.")
        return 0

    repo_root = Path(__file__).resolve().parent.parent
    failures = 0
    for i, cmd in enumerate(cmds, 1):
        print(f"\n[{i}/{len(cmds)}] Running: {' '.join(cmd)}")
        rc = subprocess.call(cmd, cwd=str(repo_root))
        if rc != 0:
            failures += 1
            print(f"  -> command failed with exit code {rc}")

    if failures:
        print(f"\nCompleted with {failures} failed batch(es).")
        return 1

    print("\nCompleted all sparse-case re-download batches successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
