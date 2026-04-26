#!/usr/bin/env python3
"""
Cloud worker for targeted cases.

Reads case IDs from a JSON file (default my_cases.json) and periodically
refreshes those specific cases with --pdf-cases.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Targeted case cloud worker")
    ap.add_argument("--cases-file", default="my_cases.json")
    ap.add_argument("--refresh-seconds", type=int, default=1800)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--download-pdfs", action="store_true")
    return ap.parse_args()


def load_case_ids(path: Path) -> list[str]:
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    case_ids: list[str] = []
    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        for item in data["cases"]:
            if isinstance(item, dict) and isinstance(item.get("case_id"), str):
                case_ids.append(item["case_id"].strip())
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                case_ids.append(item.strip())
            elif isinstance(item, dict) and isinstance(item.get("case_id"), str):
                case_ids.append(item["case_id"].strip())

    seen = set()
    unique_ids: list[str] = []
    for cid in case_ids:
        if cid and cid not in seen:
            seen.add(cid)
            unique_ids.append(cid)
    return unique_ids


def run_once(case_ids: list[str], args: argparse.Namespace) -> int:
    cmd = [
        "python3",
        "main.py",
        "scrape",
        "--start",
        "706402",
        "--limit",
        "1",
        "--direction",
        "up",
        "--workers",
        str(args.workers),
        "--pdf-cases",
        *case_ids,
    ]
    if args.headless:
        cmd.append("--headless")
    if args.download_pdfs:
        cmd.append("--download-pdfs")

    print("[targeted-worker] running:", " ".join(cmd), flush=True)
    return subprocess.run(cmd).returncode


def main() -> int:
    args = parse_args()
    cases_path = Path(args.cases_file)

    print(
        f"[targeted-worker] watching {cases_path} refresh={args.refresh_seconds}s",
        flush=True,
    )

    while True:
        try:
            case_ids = load_case_ids(cases_path)
            if not case_ids:
                print("[targeted-worker] no case IDs found; sleeping", flush=True)
                time.sleep(args.refresh_seconds)
                continue

            print(f"[targeted-worker] loaded {len(case_ids)} case IDs", flush=True)
            rc = run_once(case_ids, args)
            if rc != 0:
                print(f"[targeted-worker] scrape command failed rc={rc}", flush=True)
            time.sleep(args.refresh_seconds)
        except KeyboardInterrupt:
            print("[targeted-worker] interrupted", flush=True)
            return 0


if __name__ == "__main__":
    sys.exit(main())
