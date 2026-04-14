#!/usr/bin/env python3
"""
Daily stream orchestrator for Cuyahoga CP scraper.

Implements 3 daily streams:
1) Tracked cases refresh (with optional all-document download) and drop unchanged snapshots.
2) New cases stream (forward from latest known number per year).
3) Old missing cases stream (backfill gaps in year ranges you already have).

Usage examples:
  python scripts/daily_streams.py run
  python scripts/daily_streams.py run --headless --new-limit 20 --old-limit 20
  python scripts/daily_streams.py run --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "out"
MAIN_PY = REPO_ROOT / "main.py"


@dataclass(frozen=True)
class TrackedCase:
    case_id: str
    year: int
    number: int


DEFAULT_TRACKED_CASES = [
    TrackedCase(case_id="CR-25-706402-A", year=2025, number=706402),
    TrackedCase(case_id="CR-23-684826-A", year=2023, number=684826),
]


def run_cmd(cmd: List[str], dry_run: bool = False) -> int:
    print("$", " ".join(cmd))
    if dry_run:
        return 0
    p = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return p.returncode


def case_file_pattern(year: int, number: int) -> str:
    return f"{year}-{number:06d}_*.json"


def latest_case_files(year: int, number: int) -> List[Path]:
    year_dir = OUT_DIR / str(year)
    files = sorted(year_dir.glob(case_file_pattern(year, number)), key=lambda p: p.stat().st_mtime)
    return files


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_payload_hash(path: Path) -> str:
    """
    Hash payload while ignoring volatile scrape timestamps.
    This allows "same substantive content" dedupe after a refresh.
    """
    obj = load_json(path)

    meta = obj.get("metadata")
    if isinstance(meta, dict):
        meta.pop("scraped_at", None)

    errs = obj.get("errors")
    if isinstance(errs, list):
        for e in errs:
            if isinstance(e, dict):
                e.pop("timestamp", None)

    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def refresh_tracked_cases(
    tracked_cases: List[TrackedCase],
    delay_ms: int,
    headless: bool,
    download_all_pdfs: bool,
    dry_run: bool,
) -> List[Tuple[str, str]]:
    """
    Returns action list: (case_id, action) where action is kept|dropped|error.
    """
    actions: List[Tuple[str, str]] = []

    for tc in tracked_cases:
        before = latest_case_files(tc.year, tc.number)
        previous = before[-1] if before else None

        cmd = [
            sys.executable,
            str(MAIN_PY),
            "scrape",
            "--year",
            str(tc.year),
            "--start",
            str(tc.number),
            "--limit",
            "1",
            "--direction",
            "up",
            "--output-dir",
            "./out",
            "--delay-ms",
            str(delay_ms),
            "--workers",
            "1",
            "--download-pdfs",
            "--pdf-cases",
            tc.case_id,
        ]
        if download_all_pdfs:
            cmd.append("--all-pdfs")
        if headless:
            cmd.append("--headless")

        rc = run_cmd(cmd, dry_run=dry_run)
        if rc != 0:
            actions.append((tc.case_id, "error"))
            continue

        after = latest_case_files(tc.year, tc.number)
        if not after:
            actions.append((tc.case_id, "error"))
            continue

        newest = after[-1]
        if previous is None or newest == previous:
            actions.append((tc.case_id, "kept"))
            continue

        if dry_run:
            actions.append((tc.case_id, "kept"))
            continue

        try:
            if normalized_payload_hash(newest) == normalized_payload_hash(previous):
                newest.unlink()
                actions.append((tc.case_id, "dropped"))
            else:
                actions.append((tc.case_id, "kept"))
        except Exception:
            actions.append((tc.case_id, "kept"))

    return actions


def parse_year_num_from_filename(path: Path) -> Optional[Tuple[int, int]]:
    m = re.match(r"^(\d{4})-(\d+)_", path.name)
    if not m:
        return None
    year = int(m.group(1))
    num = int(m.group(2))
    # Filter out malformed/legacy artifacts that are not real case numbers.
    if num < 100000:
        return None
    return year, num


def get_existing_numbers_for_year(year: int) -> List[int]:
    year_dir = OUT_DIR / str(year)
    nums = []
    for p in year_dir.glob(f"{year}-*.json"):
        parsed = parse_year_num_from_filename(p)
        if parsed and parsed[0] == year:
            nums.append(parsed[1])
    return sorted(set(nums))


def scrape_numbers(year: int, numbers: List[int], delay_ms: int, headless: bool, dry_run: bool) -> int:
    if not numbers:
        return 0

    # Compress into runs to reduce process invocations.
    runs: List[Tuple[int, int]] = []
    start = numbers[0]
    prev = numbers[0]
    for n in numbers[1:]:
        if n == prev + 1:
            prev = n
            continue
        runs.append((start, prev))
        start = prev = n
    runs.append((start, prev))

    total_invocations = 0
    for a, b in runs:
        limit = b - a + 1
        cmd = [
            sys.executable,
            str(MAIN_PY),
            "scrape",
            "--year",
            str(year),
            "--start",
            str(a),
            "--limit",
            str(limit),
            "--direction",
            "up",
            "--output-dir",
            "./out",
            "--delay-ms",
            str(delay_ms),
            "--workers",
            "1",
        ]
        if headless:
            cmd.append("--headless")
        rc = run_cmd(cmd, dry_run=dry_run)
        total_invocations += 1
        if rc != 0:
            print(f"WARNING: scrape failed for {year} {a}-{b}")
    return total_invocations


def stream_new_cases(years: List[int], new_limit: int, delay_ms: int, headless: bool, dry_run: bool) -> Dict[int, List[int]]:
    picked: Dict[int, List[int]] = {}
    for year in years:
        existing = get_existing_numbers_for_year(year)
        if not existing:
            continue
        latest = max(existing)
        targets = list(range(latest + 1, latest + 1 + max(0, new_limit)))
        picked[year] = targets
        scrape_numbers(year, targets, delay_ms=delay_ms, headless=headless, dry_run=dry_run)
    return picked


def stream_old_missing_cases(years: List[int], old_limit: int, delay_ms: int, headless: bool, dry_run: bool) -> Dict[int, List[int]]:
    picked: Dict[int, List[int]] = {}
    for year in years:
        existing = get_existing_numbers_for_year(year)
        if len(existing) < 2:
            continue
        mn, mx = min(existing), max(existing)
        have = set(existing)
        missing = [n for n in range(mn, mx + 1) if n not in have]
        targets = missing[: max(0, old_limit)]
        if not targets:
            continue
        picked[year] = targets
        scrape_numbers(year, targets, delay_ms=delay_ms, headless=headless, dry_run=dry_run)
    return picked


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Daily 3-stream runner for tracked/new/missing cases")
    sub = ap.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run all 3 daily streams")
    run.add_argument("--headless", action="store_true", help="Run browser headless")
    run.add_argument("--delay-ms", type=int, default=3000, help="Delay for scraper politeness")
    run.add_argument("--new-limit", type=int, default=10, help="New-case count per year per run")
    run.add_argument("--old-limit", type=int, default=10, help="Missing-old-case count per year per run")
    run.add_argument("--years", nargs="+", type=int, default=[2026, 2025, 2024, 2023], help="Years for new/missing streams")
    run.add_argument("--tracked-case", action="append", default=[], help="Extra tracked case as CASE_ID:YEAR:NUMBER")
    run.add_argument("--je-only", action="store_true", help="For tracked cases, keep JE-only mode (default is all PDFs)")
    run.add_argument("--dry-run", action="store_true", help="Print planned commands only")

    return ap.parse_args()


def parse_tracked(extra: Iterable[str]) -> List[TrackedCase]:
    out = list(DEFAULT_TRACKED_CASES)
    for item in extra:
        try:
            cid, y, n = item.split(":")
            out.append(TrackedCase(case_id=cid, year=int(y), number=int(n)))
        except Exception:
            print(f"WARNING: invalid --tracked-case format: {item} (expected CASE_ID:YEAR:NUMBER)")
    return out


def main() -> int:
    args = parse_args()
    if args.command != "run":
        return 2

    tracked_cases = parse_tracked(args.tracked_case)

    print("=" * 90)
    print("DAILY STREAMS RUN")
    print("1) Tracked cases refresh + drop unchanged")
    print("2) New cases forward stream")
    print("3) Old missing cases backfill stream")
    print("=" * 90)

    tracked_actions = refresh_tracked_cases(
        tracked_cases=tracked_cases,
        delay_ms=args.delay_ms,
        headless=args.headless,
        download_all_pdfs=not args.je_only,
        dry_run=args.dry_run,
    )

    new_picked = stream_new_cases(
        years=args.years,
        new_limit=args.new_limit,
        delay_ms=args.delay_ms,
        headless=args.headless,
        dry_run=args.dry_run,
    )

    old_picked = stream_old_missing_cases(
        years=args.years,
        old_limit=args.old_limit,
        delay_ms=args.delay_ms,
        headless=args.headless,
        dry_run=args.dry_run,
    )

    print("\nSUMMARY")
    for case_id, action in tracked_actions:
        print(f"tracked {case_id}: {action}")

    for year in args.years:
        np = len(new_picked.get(year, []))
        op = len(old_picked.get(year, []))
        print(f"year {year}: new_targets={np} old_missing_targets={op}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
