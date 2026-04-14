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
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "out"
MAIN_PY = REPO_ROOT / "main.py"
BASE_URL = "https://cpdocket.cp.cuyahogacounty.gov"


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


def parse_hhmm(value: str) -> Tuple[int, int]:
    m = re.match(r"^(\d{2}):(\d{2})$", value.strip())
    if not m:
        raise ValueError(f"Invalid HH:MM time: {value}")
    hh = int(m.group(1))
    mm = int(m.group(2))
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        raise ValueError(f"Invalid HH:MM time: {value}")
    return hh, mm


def detect_site_activity(base_url: str = BASE_URL, timeout_sec: int = 20) -> Dict[str, object]:
    """
    Best-effort activity detection from the court Search page.

    Returns fields:
      maintenance: bool
      users_detected: bool
      no_users_detected: bool
      user_count: Optional[int]
      confidence: str (high|low)
      reason: str
    """
    url = f"{base_url}/Search.aspx"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CuyahogaDailyStreams/1.0)"})
    try:
        with urlopen(req, timeout=timeout_sec) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except (URLError, HTTPError, TimeoutError) as e:
        return {
            "maintenance": False,
            "users_detected": True,
            "no_users_detected": False,
            "user_count": None,
            "confidence": "low",
            "reason": f"site probe failed ({type(e).__name__}); staying conservative",
        }

    lower = html.lower()
    maintenance_signals = [
        "down for maintenance",
        "temporarily unavailable",
        "service unavailable",
        "scheduled maintenance",
        "currently unavailable",
    ]
    if any(sig in lower for sig in maintenance_signals):
        return {
            "maintenance": True,
            "users_detected": False,
            "no_users_detected": False,
            "user_count": None,
            "confidence": "high",
            "reason": "maintenance text detected on Search.aspx",
        }

    # Attempt to parse user/visitor activity counters.
    patterns = [
        r"(\d+)\s+(?:users?|visitors?)\s+(?:online|active)",
        r"(?:online|active)\s+(?:users?|visitors?)\D{0,16}(\d+)",
        r"(?:users?|visitors?)\s+online\D{0,16}(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, lower, flags=re.IGNORECASE)
        if m:
            count = int(m.group(1))
            return {
                "maintenance": False,
                "users_detected": count > 0,
                "no_users_detected": count == 0,
                "user_count": count,
                "confidence": "high",
                "reason": f"parsed online user count={count}",
            }

    no_user_signals = [
        "no users online",
        "0 users online",
        "no active users",
        "no visitors online",
    ]
    if any(sig in lower for sig in no_user_signals):
        return {
            "maintenance": False,
            "users_detected": False,
            "no_users_detected": True,
            "user_count": 0,
            "confidence": "high",
            "reason": "explicit no-user text detected",
        }

    # Unknown state: keep conservative to avoid overloading the site.
    return {
        "maintenance": False,
        "users_detected": True,
        "no_users_detected": False,
        "user_count": None,
        "confidence": "low",
        "reason": "no activity indicator found; staying conservative",
    }


def in_maintenance_window(window: Optional[str], now: Optional[datetime] = None) -> bool:
    if not window:
        return False
    now = now or datetime.now()
    m = re.match(r"^\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s*$", window)
    if not m:
        raise ValueError("--maintenance-window must be in format HH:MM-HH:MM")
    sh, sm = parse_hhmm(m.group(1))
    eh, em = parse_hhmm(m.group(2))
    current = now.hour * 60 + now.minute
    start = sh * 60 + sm
    end = eh * 60 + em

    # Non-wrapping window (e.g., 02:00-04:00)
    if start <= end:
        return start <= current < end
    # Wrapping window across midnight (e.g., 23:00-02:00)
    return current >= start or current < end


def load_state(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {"consecutive_errors": 0, "cooldown_until": None, "last_run": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("state must be JSON object")
        data.setdefault("consecutive_errors", 0)
        data.setdefault("cooldown_until", None)
        data.setdefault("last_run", None)
        return data
    except Exception:
        return {"consecutive_errors": 0, "cooldown_until": None, "last_run": None}


def save_state(path: Path, state: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


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


def scrape_numbers(year: int, numbers: List[int], delay_ms: int, workers: int, headless: bool, dry_run: bool) -> Tuple[int, int]:
    if not numbers:
        return 0, 0

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
    failed_invocations = 0
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
            str(max(1, workers)),
        ]
        if headless:
            cmd.append("--headless")
        rc = run_cmd(cmd, dry_run=dry_run)
        total_invocations += 1
        if rc != 0:
            print(f"WARNING: scrape failed for {year} {a}-{b}")
            failed_invocations += 1
    return total_invocations, failed_invocations


def stream_new_cases(years: List[int], new_limit: int, delay_ms: int, workers: int, headless: bool, dry_run: bool) -> Tuple[Dict[int, List[int]], int]:
    picked: Dict[int, List[int]] = {}
    failed_invocations = 0
    for year in years:
        existing = get_existing_numbers_for_year(year)
        if not existing:
            continue
        latest = max(existing)
        targets = list(range(latest + 1, latest + 1 + max(0, new_limit)))
        picked[year] = targets
        _, failed = scrape_numbers(year, targets, delay_ms=delay_ms, workers=workers, headless=headless, dry_run=dry_run)
        failed_invocations += failed
    return picked, failed_invocations


def stream_old_missing_cases(years: List[int], old_limit: int, delay_ms: int, workers: int, headless: bool, dry_run: bool) -> Tuple[Dict[int, List[int]], int]:
    picked: Dict[int, List[int]] = {}
    failed_invocations = 0
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
        _, failed = scrape_numbers(year, targets, delay_ms=delay_ms, workers=workers, headless=headless, dry_run=dry_run)
        failed_invocations += failed
    return picked, failed_invocations


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Daily 3-stream runner for tracked/new/missing cases")
    sub = ap.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run all 3 daily streams")
    run.add_argument("--headless", action="store_true", help="Run browser headless")
    run.add_argument("--delay-ms", type=int, default=3000, help="Delay for scraper politeness")
    run.add_argument("--workers", type=int, default=1, help="Workers for new/old case streams")
    run.add_argument("--new-limit", type=int, default=10, help="New-case count per year per run")
    run.add_argument("--old-limit", type=int, default=10, help="Missing-old-case count per year per run")
    run.add_argument("--years", nargs="+", type=int, default=[2026, 2025, 2024, 2023], help="Years for new/missing streams")
    run.add_argument("--tracked-case", action="append", default=[], help="Extra tracked case as CASE_ID:YEAR:NUMBER")
    run.add_argument("--je-only", action="store_true", help="For tracked cases, keep JE-only mode (default is all PDFs)")
    run.add_argument("--maintenance-window", default="", help="Optional local quiet window HH:MM-HH:MM to skip runs")
    run.add_argument("--adaptive-site-load", action="store_true", help="If no users are detected on court site, temporarily run in full-throttle mode")
    run.add_argument("--full-throttle-delay-ms", type=int, default=1200, help="Delay when adaptive mode enters full throttle")
    run.add_argument("--full-throttle-workers", type=int, default=3, help="Workers when adaptive mode enters full throttle")
    run.add_argument("--full-throttle-new-limit", type=int, default=8, help="New-case limit per year in full throttle")
    run.add_argument("--full-throttle-old-limit", type=int, default=8, help="Old-missing limit per year in full throttle")
    run.add_argument("--state-file", default="./logs/daily_streams_state.json", help="Persistent state file for error cooldown")
    run.add_argument("--error-threshold", type=int, default=3, help="Consecutive failed runs before cooldown")
    run.add_argument("--cooldown-minutes", type=int, default=120, help="Cooldown duration after repeated errors")
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

    if in_maintenance_window(args.maintenance_window):
        print(f"Skipping run: inside maintenance window {args.maintenance_window}")
        return 0

    effective_delay_ms = args.delay_ms
    effective_workers = max(1, args.workers)
    effective_new_limit = args.new_limit
    effective_old_limit = args.old_limit

    if args.adaptive_site_load:
        activity = detect_site_activity()
        print(
            "site_activity:",
            f"maintenance={activity.get('maintenance')}",
            f"users_detected={activity.get('users_detected')}",
            f"no_users_detected={activity.get('no_users_detected')}",
            f"user_count={activity.get('user_count')}",
            f"confidence={activity.get('confidence')}",
            f"reason={activity.get('reason')}",
        )
        if activity.get("maintenance"):
            print("Skipping run: site-side maintenance detected")
            return 0
        if activity.get("no_users_detected"):
            effective_delay_ms = args.full_throttle_delay_ms
            effective_workers = max(1, args.full_throttle_workers)
            effective_new_limit = max(0, args.full_throttle_new_limit)
            effective_old_limit = max(0, args.full_throttle_old_limit)
            print(
                "adaptive_mode: full_throttle",
                f"delay_ms={effective_delay_ms}",
                f"workers={effective_workers}",
                f"new_limit={effective_new_limit}",
                f"old_limit={effective_old_limit}",
            )
        else:
            print(
                "adaptive_mode: conservative",
                f"delay_ms={effective_delay_ms}",
                f"workers={effective_workers}",
                f"new_limit={effective_new_limit}",
                f"old_limit={effective_old_limit}",
            )

    state_path = (REPO_ROOT / args.state_file).resolve() if not Path(args.state_file).is_absolute() else Path(args.state_file)
    state = load_state(state_path)
    now = datetime.now()
    cooldown_until_raw = state.get("cooldown_until")
    if isinstance(cooldown_until_raw, str):
        try:
            cooldown_until = datetime.fromisoformat(cooldown_until_raw)
            if now < cooldown_until:
                print(f"Skipping run: cooldown active until {cooldown_until.isoformat(timespec='seconds')}")
                return 0
        except Exception:
            pass

    print("=" * 90)
    print("DAILY STREAMS RUN")
    print("1) Tracked cases refresh + drop unchanged")
    print("2) New cases forward stream")
    print("3) Old missing cases backfill stream")
    print("=" * 90)

    tracked_actions = refresh_tracked_cases(
        tracked_cases=tracked_cases,
        delay_ms=effective_delay_ms,
        headless=args.headless,
        download_all_pdfs=not args.je_only,
        dry_run=args.dry_run,
    )

    new_picked, new_failures = stream_new_cases(
        years=args.years,
        new_limit=effective_new_limit,
        delay_ms=effective_delay_ms,
        workers=effective_workers,
        headless=args.headless,
        dry_run=args.dry_run,
    )

    old_picked, old_failures = stream_old_missing_cases(
        years=args.years,
        old_limit=effective_old_limit,
        delay_ms=effective_delay_ms,
        workers=effective_workers,
        headless=args.headless,
        dry_run=args.dry_run,
    )

    tracked_errors = sum(1 for _, action in tracked_actions if action == "error")
    had_errors = tracked_errors > 0 or new_failures > 0 or old_failures > 0

    print("\nSUMMARY")
    for case_id, action in tracked_actions:
        print(f"tracked {case_id}: {action}")

    for year in args.years:
        np = len(new_picked.get(year, []))
        op = len(old_picked.get(year, []))
        print(f"year {year}: new_targets={np} old_missing_targets={op}")

    # Update persistent error/cooldown state.
    consecutive = int(state.get("consecutive_errors", 0) or 0)
    if had_errors:
        consecutive += 1
        print(f"run_status: errors_detected tracked_errors={tracked_errors} new_failures={new_failures} old_failures={old_failures} consecutive_errors={consecutive}")
        state["consecutive_errors"] = consecutive
        if consecutive >= max(1, args.error_threshold):
            cooldown_until = now + timedelta(minutes=max(1, args.cooldown_minutes))
            state["cooldown_until"] = cooldown_until.isoformat(timespec="seconds")
            print(f"cooldown_enabled_until: {state['cooldown_until']}")
    else:
        state["consecutive_errors"] = 0
        state["cooldown_until"] = None
        print("run_status: ok")

    state["last_run"] = now.isoformat(timespec="seconds")
    save_state(state_path, state)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
