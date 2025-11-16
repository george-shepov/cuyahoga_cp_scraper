#!/usr/bin/env python3
"""Retry downloading invalid case JSONs listed in scripts/validation.log.

Conservative defaults: processes up to --max cases (default 30), sequentially, with a small delay.
Usage: python3 scripts/retry_invalid.py --max 30
Options:
  --log PATH    Path to validation log (default: scripts/validation.log)
  --max N       Max unique cases to retry (default: 30)
  --dry-run     Print plan but do not perform downloads
  --delay S     Seconds to sleep between retries (default: 1)
  --limit       How many cases to pass to scraper per invocation (default: 1)
"""
import argparse
import re
from pathlib import Path
import subprocess
import time
from collections import OrderedDict

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / 'scripts' / 'validation.log'
RETRY_LOG = ROOT / 'scripts' / 'retry_invalid.log'


def parse_invalids(path: Path):
    """Return ordered list of (year, case) tuples from the validation log."""
    if not path.exists():
        return []
    text = path.read_text(encoding='utf-8', errors='ignore')
    # Look for lines like: "... INVALID /home/.../out/2025/2025-706810_20251112_115235.json"
    pattern = re.compile(r'INVALID\s+([^\s]+out[\\/](\d{4})[\\/](\d{4}-)?(\d{6})[^\s]*)')
    seen = OrderedDict()
    for m in pattern.finditer(text):
        fullpath = m.group(1)
        year = m.group(2)
        case_num = m.group(4)
        key = (int(year), int(case_num))
        if key not in seen:
            seen[key] = fullpath
    return list(seen.items())


def run_retry(entries, dry_run=False, delay=1, limit=1):
    RETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RETRY_LOG, 'a') as outfh:
        outfh.write(f"# Retry run: {time.ctime()}\n")
        for (year, case_num), src in entries:
            cmd = ["python3", "main.py", "scrape", "--resume", "--year", str(year), "--start", str(case_num), "--limit", str(limit), "--delay-ms", "1250"]
            outfh.write(f"RUNNING: {' '.join(cmd)}  # source={src}\n")
            outfh.flush()
            print(f"Retrying {year}-{case_num:06d} -> {'DRY' if dry_run else 'RUN'}")
            if dry_run:
                continue
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                outfh.write(f"EXIT={r.returncode}\nSTDOUT:\n{r.stdout[:2000]}\nSTDERR:\n{r.stderr[:2000]}\n---\n")
            except Exception as e:
                outfh.write(f"EXCEPTION: {e}\n")
            time.sleep(delay)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--log', type=Path, default=LOG)
    p.add_argument('--max', type=int, default=30)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--delay', type=float, default=1.0)
    p.add_argument('--limit', type=int, default=1)
    args = p.parse_args()

    entries = parse_invalids(args.log)
    if not entries:
        print(f"No invalid entries found in {args.log}")
        return

    print(f"Found {len(entries)} unique invalid cases; will retry up to {args.max}")
    to_retry = entries[:args.max]
    for (y, c), src in to_retry:
        print(f"  -> {y}-{c:06d} (from {src})")

    run_retry(to_retry, dry_run=args.dry_run, delay=args.delay, limit=args.limit)
    print(f"Retry pass complete; details in {RETRY_LOG}")


if __name__ == '__main__':
    main()
