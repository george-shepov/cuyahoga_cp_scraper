#!/usr/bin/env python3
"""
Main-node tiered refresh scheduler.

Tiers:
- daily: current year (forward updates) + manual cases
- every3d: previous year through previous-5 (backfill windows) + manual cases
- weekly: all older years (backfill windows) + manual cases

PDF policy:
- Download only indictment/bindover style docket PDFs by type filter (default: CR)
- Do NOT pull all PDFs.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "out"
STATE_FILE = REPO_ROOT / "state" / "main_node_tier_state.json"
CASE_ID_RE = re.compile(r"^CR-(\d{2})-(\d{6})-[A-Z]$")


def latest_case_number_for_year(year: int) -> int:
    year_dir = OUT_ROOT / str(year)
    if not year_dir.exists():
        return 0
    best = 0
    for p in year_dir.glob(f"{year}-*.json"):
        try:
            num = int(p.name.split("_")[0].split("-")[1])
        except Exception:
            continue
        best = max(best, num)
    return best


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"years": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"years": {}}


def save_state(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def run(cmd: list[str]) -> int:
    print("[tiered] RUN:", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


def parse_manual_cases(path: Path) -> list[tuple[int, int, str]]:
    if not path.exists():
        return []
    out: list[tuple[int, int, str]] = []

    if path.suffix.lower() == ".json":
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            obj = None

        vals: list[str] = []
        if isinstance(obj, list):
            for x in obj:
                if isinstance(x, str):
                    vals.append(x)
                elif isinstance(x, dict) and isinstance(x.get("case_id"), str):
                    vals.append(x["case_id"])
        elif isinstance(obj, dict):
            arr = obj.get("cases")
            if isinstance(arr, list):
                for x in arr:
                    if isinstance(x, str):
                        vals.append(x)
                    elif isinstance(x, dict) and isinstance(x.get("case_id"), str):
                        vals.append(x["case_id"])

        for cid in vals:
            m = CASE_ID_RE.match(cid.strip().upper())
            if not m:
                continue
            year = 2000 + int(m.group(1))
            num = int(m.group(2))
            out.append((year, num, cid.strip().upper()))
        return out

    # txt/csv style: one case id per line
    for line in path.read_text(encoding="utf-8").splitlines():
        cid = line.strip().upper()
        if not cid or cid.startswith("#"):
            continue
        m = CASE_ID_RE.match(cid)
        if not m:
            continue
        year = 2000 + int(m.group(1))
        num = int(m.group(2))
        out.append((year, num, cid))
    return out


def tier_years(tier: str, available_years: list[int], current_year: int) -> list[int]:
    if tier == "daily":
        return [current_year]
    if tier == "every3d":
        return [y for y in [current_year - 1, current_year - 2, current_year - 3, current_year - 4, current_year - 5] if y in available_years]
    # weekly
    return [y for y in available_years if y <= current_year - 6]


def main() -> int:
    ap = argparse.ArgumentParser(description="Tiered main-node refresh")
    ap.add_argument("--tier", choices=["daily", "every3d", "weekly"], required=True)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--delay-ms", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--forward-limit", type=int, default=50)
    ap.add_argument("--backfill-batch", type=int, default=40)
    ap.add_argument("--pdf-types", nargs="*", default=["CR"])
    ap.add_argument("--manual-cases-file", default="my_cases.json")
    ap.add_argument("--state-file", default=str(STATE_FILE))
    args = ap.parse_args()

    current_year = datetime.now().year
    available_years = sorted([int(p.name) for p in OUT_ROOT.iterdir() if p.is_dir() and p.name.isdigit()])
    years = tier_years(args.tier, available_years, current_year)

    state_path = Path(args.state_file)
    state = load_state(state_path)
    state.setdefault("years", {})

    # Current year forward updates (latest new filings)
    if args.tier == "daily":
        yk = str(current_year)
        ystate = state["years"].setdefault(yk, {})
        last_forward = int(ystate.get("last_forward", 0))
        if last_forward <= 0:
            last_forward = latest_case_number_for_year(current_year)
        start = last_forward + 1

        cmd = [
            sys.executable,
            "main.py",
            "scrape",
            "--year",
            str(current_year),
            "--start",
            str(start),
            "--limit",
            str(args.forward_limit),
            "--direction",
            "up",
            "--delay-ms",
            str(args.delay_ms),
            "--workers",
            str(args.workers),
            "--download-pdfs",
            "--pdf-types",
            *args.pdf_types,
        ]
        if args.headless:
            cmd.append("--headless")
        run(cmd)
        ystate["last_forward"] = latest_case_number_for_year(current_year)

    # Year-by-year historical backfill (indictment/bindover pdf types only)
    for year in years:
        yk = str(year)
        ystate = state["years"].setdefault(yk, {})
        next_backfill = int(ystate.get("next_backfill", 0))
        if next_backfill <= 0:
            next_backfill = latest_case_number_for_year(year)

        if next_backfill <= 0:
            continue

        cmd = [
            sys.executable,
            "main.py",
            "scrape",
            "--year",
            str(year),
            "--start",
            str(next_backfill),
            "--limit",
            str(args.backfill_batch),
            "--direction",
            "down",
            "--delay-ms",
            str(args.delay_ms),
            "--workers",
            str(args.workers),
            "--download-pdfs",
            "--pdf-types",
            *args.pdf_types,
        ]
        if args.headless:
            cmd.append("--headless")
        run(cmd)
        ystate["next_backfill"] = max(0, next_backfill - args.backfill_batch)

    # Manual case overrides
    manual_cases = parse_manual_cases(Path(args.manual_cases_file))
    for year, num, case_id in manual_cases:
        cmd = [
            sys.executable,
            "main.py",
            "scrape",
            "--year",
            str(year),
            "--start",
            str(num),
            "--limit",
            "1",
            "--direction",
            "up",
            "--delay-ms",
            str(args.delay_ms),
            "--workers",
            "1",
            "--download-pdfs",
            "--pdf-types",
            *args.pdf_types,
        ]
        if args.headless:
            cmd.append("--headless")
        run(cmd)

    save_state(state_path, state)
    print(f"[tiered] done tier={args.tier} years={years} manual_cases={len(manual_cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
