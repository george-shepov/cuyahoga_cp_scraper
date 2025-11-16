#!/usr/bin/env python3
"""Simple manager/orchestrator for running multiple scraper workers and periodic rechecks.

This script is intended to be run on a VPS. It will:
 - Launch N concurrent scraper worker subprocesses (each runs a small chunk via main.py)
 - Periodically run validation (scripts/validate_cache.py)
 - Periodically run the stats collector (scripts/stats_collector.py)
 - Optionally perform recheck cycles for recently-downloaded cases to detect docket changes

Usage: python3 scripts/manager.py --workers 8
"""
import argparse
import subprocess
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
import threading

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


def run_worker(worker_id: int, args):
    """Each worker runs sequential scrape invocations with modest limits to avoid huge memory usage."""
    console_prefix = f"[worker-{worker_id}]"
    print(f"{console_prefix} starting")

    # a simple loop: invoke main.py scrape with --resume and a small --limit
    while True:
        cmd = ["python3", "main.py", "scrape", "--resume", "--limit", str(args.chunk), "--delay-ms", str(args.delay_ms)]
        if args.headless:
            cmd.append("--headless")
        # Set YEAR env to focus on 2025 first
        env = os.environ.copy()
        env['YEAR'] = str(args.year)
        print(f"{console_prefix} running: {' '.join(cmd)} (env YEAR={env['YEAR']})")
        p = subprocess.Popen(cmd, env=env)
        p.wait()
        print(f"{console_prefix} finished a chunk (exit={p.returncode}). Sleeping {args.pause_between_chunks}s")
        time.sleep(args.pause_between_chunks)


def periodic_task(interval, func, *a, **kw):
    def loop():
        while True:
            try:
                func(*a, **kw)
            except Exception as e:
                print(f"Periodic task error: {e}")
            time.sleep(interval)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t


def run_validator():
    cmd = ["python3", str(ROOT / 'scripts' / 'validate_cache.py'), '--years', '2025', '2024', '2023']
    print(f"[validator] running: {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(f"[validator] exit={r.returncode}, stdout(len)={len(r.stdout)}, stderr(len)={len(r.stderr)}")


def run_collector():
    cmd = ["python3", str(ROOT / 'scripts' / 'stats_collector.py')]
    print(f"[collector] running: {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(f"[collector] exit={r.returncode}, stdout(len)={len(r.stdout)}")


def recheck_recent(days=1, sample=200):
    """Trigger rechecks: re-run scraper for a sample of most recently-downloaded cases to detect changes.

    This function is conservative: it picks up to `sample` most recent unique case numbers and
    runs `main.py scrape` for each case with limit=1 to refresh the case. The scraper will
    save a new JSON file; the stats collector will detect differences.
    """
    print(f"[recheck] scanning for recent files (last {days} days)")
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = []
    for y in [2025, 2024, 2023]:
        d = OUT / str(y)
        if not d.exists():
            continue
        files = sorted(d.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files:
            if len(recent) >= sample:
                break
            mtime = datetime.utcfromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                continue
            # extract case number from filename pattern YEAR-######_TIMESTAMP.json
            parts = f.name.split('_', 1)[0].split('-')
            if len(parts) >= 2:
                case_num = parts[1]
                recent.append((y, case_num))
        if len(recent) >= sample:
            break

    # deduplicate by case
    seen = set()
    to_recheck = []
    for y, c in recent:
        key = f"{y}-{c}"
        if key in seen:
            continue
        seen.add(key)
        to_recheck.append((y, int(c)))

    print(f"[recheck] rechecking {len(to_recheck)} cases (sample) via main.py")
    for y, c in to_recheck:
        cmd = ["python3", "main.py", "scrape", "--resume", "--year", str(y), "--start", str(c), "--limit", "1", "--delay-ms", "1000"]
        print(f"[recheck] running: {' '.join(cmd)}")
        r = subprocess.run(cmd)
        print(f"[recheck] case {y}-{c:06d} exit={r.returncode}")
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--chunk', type=int, default=50, help='cases per invocation of main.py')
    parser.add_argument('--pause-between-chunks', type=int, default=5, dest='pause_between_chunks')
    parser.add_argument('--delay-ms', type=int, default=1250)
    parser.add_argument('--year', type=int, default=2025)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--validate-interval', type=int, default=15*60)
    parser.add_argument('--collect-interval', type=int, default=60*60)
    parser.add_argument('--recheck-interval', type=int, default=6*60*60)
    args = parser.parse_args()

    print(f"manager starting: workers={args.workers} chunk={args.chunk} year={args.year}")

    # start worker threads
    for i in range(args.workers):
        t = threading.Thread(target=run_worker, args=(i+1, args), daemon=True)
        t.start()

    # start periodic validator
    periodic_task(args.validate_interval, run_validator)

    # start periodic stats collector
    periodic_task(args.collect_interval, run_collector)

    # start periodic recheck
    periodic_task(args.recheck_interval, recheck_recent, 1, 200)

    # block forever
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print('manager exiting')


if __name__ == '__main__':
    main()
