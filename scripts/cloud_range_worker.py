#!/usr/bin/env python3
"""
Cloud worker for continuous numeric range mining.

Runs main.py scrape in repeated batches while persisting a cursor file so each
worker can resume independently after restart.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Continuous forward/backward cloud range worker")
    ap.add_argument("--direction", choices=["up", "down"], required=True)
    ap.add_argument("--start", type=int, required=True, help="Initial case number")
    ap.add_argument("--limit", type=int, default=200, help="Batch size per scrape call")
    ap.add_argument("--workers", type=int, default=6, help="main.py worker count")
    ap.add_argument("--delay", type=int, default=20, help="Seconds between batches")
    ap.add_argument("--cursor-file", required=True, help="Path to persisted cursor file")
    ap.add_argument("--min-case", type=int, default=1)
    ap.add_argument("--max-case", type=int, default=1_000_000)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--download-pdfs", action="store_true")
    ap.add_argument("--year", type=int, default=None, help="Optional fixed year")
    return ap.parse_args()


def load_cursor(path: Path, default_start: int) -> int:
    if not path.exists():
        return default_start
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return default_start


def save_cursor(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(value), encoding="utf-8")


def build_cmd(cursor: int, args: argparse.Namespace) -> list[str]:
    cmd = [
        "python3",
        "main.py",
        "scrape",
        "--start",
        str(cursor),
        "--limit",
        str(args.limit),
        "--direction",
        args.direction,
        "--workers",
        str(args.workers),
    ]
    if args.year is not None:
        cmd.extend(["--year", str(args.year)])
    if args.headless:
        cmd.append("--headless")
    if args.download_pdfs:
        cmd.append("--download-pdfs")
    return cmd


def advance_cursor(cursor: int, args: argparse.Namespace) -> int:
    if args.direction == "up":
        return min(cursor + args.limit, args.max_case)
    return max(cursor - args.limit, args.min_case)


def reached_boundary(cursor: int, args: argparse.Namespace) -> bool:
    if args.direction == "up":
        return cursor >= args.max_case
    return cursor <= args.min_case


def run_forever(args: argparse.Namespace) -> int:
    cursor_path = Path(args.cursor_file)
    cursor = load_cursor(cursor_path, args.start)
    print(
        f"[range-worker] start direction={args.direction} cursor={cursor} "
        f"limit={args.limit} workers={args.workers}",
        flush=True,
    )

    while True:
        if reached_boundary(cursor, args):
            print(f"[range-worker] boundary reached at {cursor}, sleeping {args.delay}s", flush=True)
            time.sleep(args.delay)
            continue

        cmd = build_cmd(cursor, args)
        print("[range-worker] running:", " ".join(cmd), flush=True)
        result = subprocess.run(cmd)

        next_cursor = advance_cursor(cursor, args)
        save_cursor(cursor_path, next_cursor)
        cursor = next_cursor

        if result.returncode != 0:
            print(
                f"[range-worker] scrape command failed rc={result.returncode}; "
                f"sleeping {args.delay}s",
                flush=True,
            )
        time.sleep(args.delay)


def main() -> int:
    args = parse_args()
    try:
        return run_forever(args)
    except KeyboardInterrupt:
        print("[range-worker] interrupted", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
