#!/usr/bin/env python3
"""Watchdog to keep the downloader alive and ensure out/ is growing.

This script is a conservative watchdog that:
- checks file counts every 15 minutes,
- if counts didn't change and a provided "check_command" is given, it runs that command (e.g., restart scraper),
- writes a small rotating log to scripts/watchdog.log.

It's intentionally minimal — integrate with systemd or cron for production.

Usage: python3 scripts/watchdog_scraper.py --check-cmd "python3 scraper.py --resume"
Or run without --check-cmd and it will only report counts.
"""
import argparse
import subprocess
import time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
LOG = ROOT / "scripts" / "watchdog.log"


def year_counts():
    counts = {}
    for y in (2023, 2024, 2025):
        d = OUT / str(y)
        if not d.exists():
            counts[y] = 0
            continue
        counts[y] = sum(1 for _ in d.glob('*.json'))
    return counts


def log(msg: str):
    s = f"{datetime.utcnow().isoformat()}Z {msg}\n"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, 'a') as fh:
        fh.write(s)
    print(s, end='')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--interval', type=int, default=15*60, help='seconds between checks (default 900)')
    p.add_argument('--check-cmd', type=str, default=None, help='command to run when counts stagnant')
    p.add_argument('--validate', action='store_true', help='run validation on newly added files using scripts/validate_cache.py')
    p.add_argument('--stagnant-threshold', type=int, default=1, help='how many checks in a row to consider stagnant')
    args = p.parse_args()

    prev = year_counts()
    stagnant = 0
    log(f"watchdog start; initial counts={prev}")
    while True:
        time.sleep(args.interval)
        cur = year_counts()
        changed = any(cur[y] != prev[y] for y in cur)
        log(f"counts: {cur} (changed={changed})")
        if changed:
            stagnant = 0
            prev = cur
            continue
        stagnant += 1
        log(f"no change detected (stagnant={stagnant})")
        if stagnant >= args.stagnant_threshold and args.check_cmd:
            log(f"stagnation threshold reached; running: {args.check_cmd}")
            try:
                r = subprocess.run(args.check_cmd, shell=True, capture_output=True, text=True, timeout=300)
                log(f"check_cmd exit={r.returncode}; stdout={r.stdout[:1000]!r}; stderr={r.stderr[:1000]!r}")
            except Exception as e:
                log(f"check_cmd failed: {e}")
            # after attempting restart, reset prev to current to avoid repeated restarts
            prev = year_counts()
            stagnant = 0
        # Optionally run validation on newly added files
        if args.validate:
            try:
                validate_cmd = f"python3 {ROOT / 'scripts' / 'validate_cache.py'} --years 2025 2024 2023"
                log(f"running validator: {validate_cmd}")
                vr = subprocess.run(validate_cmd, shell=True, capture_output=True, text=True, timeout=600)
                log(f"validate exit={vr.returncode}; stdout={vr.stdout[:1000]!r}; stderr={vr.stderr[:1000]!r}")
                # If validator found invalid files, exit code 2 - optionally trigger restart
                if vr.returncode == 2 and args.check_cmd:
                    log("validator found invalid files; attempting configured check-cmd")
                    try:
                        r2 = subprocess.run(args.check_cmd, shell=True, capture_output=True, text=True, timeout=300)
                        log(f"post-validate check_cmd exit={r2.returncode}; stdout={r2.stdout[:1000]!r}; stderr={r2.stderr[:1000]!r}")
                    except Exception as e:
                        log(f"post-validate check_cmd failed: {e}")
            except Exception as e:
                log(f"validator execution failed: {e}")


if __name__ == '__main__':
    main()
