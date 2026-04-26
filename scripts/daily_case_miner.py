#!/usr/bin/env python3
"""
Daily incremental case miner for Brockler Case Intelligence.

What it does on each run:
1) Reads miner state (last year/number/date).
2) Scrapes forward from last_number + 1 for the current year.
3) Updates state with the highest case number found.
4) Pushes refreshed case intelligence payload to /cases-sync.

State is stored in JSON and includes date markers so the node always knows
what day it last ran and where to resume (+1 progression).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "out"
DEFAULT_STATE = REPO_ROOT / "state" / "case_miner_state.json"
FILENAME_RE = re.compile(r"^(\d{4})-(\d{6})_(\d{8}_\d{6})\.json$")


@dataclass
class MinerState:
    year: int
    last_case_number: int
    last_run_at: str
    last_run_date: str
    runs: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "last_case_number": self.last_case_number,
            "last_run_at": self.last_run_at,
            "last_run_date": self.last_run_date,
            "runs": self.runs,
        }


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_ymd() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def latest_case_number_for_year(year: int) -> int | None:
    year_dir = OUT_ROOT / str(year)
    if not year_dir.exists():
        return None

    latest_by_number: dict[int, str] = {}
    for p in year_dir.glob(f"{year}-*.json"):
        m = FILENAME_RE.match(p.name)
        if not m:
            continue
        n = int(m.group(2))
        ts = m.group(3)
        prev = latest_by_number.get(n)
        if prev is None or ts > prev:
            latest_by_number[n] = ts

    if not latest_by_number:
        return None
    return max(latest_by_number)


def load_state(path: Path, target_year: int) -> MinerState:
    if path.exists():
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            return MinerState(
                year=int(obj.get("year", target_year)),
                last_case_number=int(obj.get("last_case_number", 0)),
                last_run_at=str(obj.get("last_run_at", "")),
                last_run_date=str(obj.get("last_run_date", "")),
                runs=int(obj.get("runs", 0)),
            )
        except (ValueError, TypeError, json.JSONDecodeError):
            pass

    inferred = latest_case_number_for_year(target_year) or 0
    return MinerState(
        year=target_year,
        last_case_number=inferred,
        last_run_at="",
        last_run_date="",
        runs=0,
    )


def save_state(path: Path, state: MinerState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def run_cmd(cmd: list[str], cwd: Path) -> int:
    print("[miner] RUN:", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def push_cases(host: str, days: int, token: str | None) -> int:
    cmd = [
        sys.executable,
        "scripts/push_brockler_cases.py",
        "--host",
        host,
        "--days",
        str(days),
    ]
    env = None
    if token:
        env = dict(**__import__("os").environ)
        env["BROCKLER_API_TOKEN"] = token
    print("[miner] RUN:", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=str(REPO_ROOT), env=env).returncode


def build_cases_payload(days: int, include_vacant: bool = False) -> dict[str, Any]:
    from push_brockler_cases import collect_cases

    brockler, vacant = collect_cases(days)
    if not include_vacant:
        vacant = []

    return {
        "brockler_cases": brockler,
        "vacant_cases": vacant,
        "synced_at": now_utc_iso(),
    }


def deploy_cases_via_ssh(payload: dict[str, Any], ssh_host: str, ssh_key: str, remote_cases_file: str) -> int:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(payload, tmp, indent=2)
        tmp_path = Path(tmp.name)

    remote_tmp = f"/tmp/{tmp_path.name}"
    scp_cmd = [
        "scp",
        "-i",
        ssh_key,
        "-o",
        "ConnectTimeout=12",
        "-o",
        "StrictHostKeyChecking=no",
        str(tmp_path),
        f"{ssh_host}:{remote_tmp}",
    ]
    print("[miner] RUN:", " ".join(scp_cmd), flush=True)
    scp_rc = subprocess.run(scp_cmd, cwd=str(REPO_ROOT)).returncode
    if scp_rc != 0:
        return scp_rc

    remote_dir = str(Path(remote_cases_file).parent)
    ssh_cmd = [
        "ssh",
        "-i",
        ssh_key,
        "-o",
        "ConnectTimeout=12",
        "-o",
        "StrictHostKeyChecking=no",
        ssh_host,
        (
            f"mkdir -p {remote_dir} && "
            f"mv {remote_tmp} {remote_cases_file} && "
            f"chown www-data:www-data {remote_cases_file}"
        ),
    ]
    print("[miner] RUN:", " ".join(ssh_cmd), flush=True)
    ssh_rc = subprocess.run(ssh_cmd, cwd=str(REPO_ROOT)).returncode
    try:
        tmp_path.unlink(missing_ok=True)
    except OSError:
        pass
    return ssh_rc


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily incremental case miner")
    ap.add_argument("--state-file", default=str(DEFAULT_STATE))
    ap.add_argument("--year", type=int, default=datetime.now().year)
    ap.add_argument("--daily-limit", type=int, default=150)
    ap.add_argument("--delay-ms", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--download-pdfs", action="store_true")
    ap.add_argument("--pdf-types", nargs="*", default=[])
    ap.add_argument("--push-host", default="https://prosecutordefense.com")
    ap.add_argument("--vacant-days", type=int, default=90)
    ap.add_argument("--include-vacant", action="store_true")
    ap.add_argument("--token", default="")
    ap.add_argument("--sync-mode", choices=["api", "ssh"], default="ssh")
    ap.add_argument("--ssh-host", default="root@104.237.2.186")
    ap.add_argument("--ssh-key", default=str(Path.home() / ".ssh" / "vps_dime_key"))
    ap.add_argument("--remote-cases-file", default="/opt/brocklerlaw-save/cases_data.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    state_path = Path(args.state_file)
    state = load_state(state_path, args.year)

    # If year rolls over, keep progression logic but switch to current year.
    if state.year != args.year:
        inferred = latest_case_number_for_year(args.year)
        state.year = args.year
        state.last_case_number = inferred if inferred is not None else max(0, state.last_case_number)

    start_num = state.last_case_number + 1
    print(
        f"[miner] state year={state.year} last_case={state.last_case_number} "
        f"last_run={state.last_run_date or 'never'} -> start={start_num}",
        flush=True,
    )

    if args.dry_run:
        print("[miner] dry-run only; no scrape/push executed", flush=True)
        return 0

    scrape_cmd = [
        sys.executable,
        "main.py",
        "scrape",
        "--year",
        str(state.year),
        "--start",
        str(start_num),
        "--limit",
        str(args.daily_limit),
        "--direction",
        "up",
        "--delay-ms",
        str(args.delay_ms),
        "--workers",
        str(args.workers),
    ]
    if args.headless:
        scrape_cmd.append("--headless")
    if args.download_pdfs:
        scrape_cmd.append("--download-pdfs")
    if args.pdf_types:
        scrape_cmd.extend(["--pdf-types", *args.pdf_types])

    rc = run_cmd(scrape_cmd, REPO_ROOT)
    if rc != 0:
        print(f"[miner] scrape failed rc={rc}", flush=True)
        return rc

    latest = latest_case_number_for_year(state.year)
    if latest is not None and latest > state.last_case_number:
        state.last_case_number = latest

    if args.sync_mode == "api":
        push_rc = push_cases(args.push_host, args.vacant_days, args.token or None)
    else:
        payload = build_cases_payload(args.vacant_days, include_vacant=args.include_vacant)
        push_rc = deploy_cases_via_ssh(payload, args.ssh_host, args.ssh_key, args.remote_cases_file)

    if push_rc != 0:
        print(f"[miner] cases sync failed rc={push_rc}", flush=True)
        return push_rc

    state.last_run_at = now_utc_iso()
    state.last_run_date = today_ymd()
    state.runs += 1
    save_state(state_path, state)

    print(
        f"[miner] done: year={state.year} last_case={state.last_case_number} "
        f"runs={state.runs} state={state_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
