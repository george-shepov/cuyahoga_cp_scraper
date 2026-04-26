#!/usr/bin/env python3
"""
Build Case Intelligence payload and push it directly to node via SSH.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from push_brockler_cases import collect_cases


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync cases payload to node over SSH")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--include-vacant", action="store_true")
    ap.add_argument("--ssh-host", default="root@104.237.2.186")
    ap.add_argument("--ssh-key", default=str(Path.home() / ".ssh" / "vps_dime_key"))
    ap.add_argument("--remote-cases-file", default="/opt/brocklerlaw-save/cases_data.json")
    args = ap.parse_args()

    brockler, vacant = collect_cases(args.days)
    if not args.include_vacant:
        vacant = []
    payload = {
        "brockler_cases": brockler,
        "vacant_cases": vacant,
        "synced_at": now_iso(),
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(payload, tmp, indent=2)
        local_path = Path(tmp.name)

    remote_tmp = f"/tmp/{local_path.name}"
    remote_file = args.remote_cases_file
    remote_dir = str(Path(remote_file).parent)

    scp_cmd = [
        "scp",
        "-i",
        args.ssh_key,
        "-o",
        "ConnectTimeout=12",
        "-o",
        "StrictHostKeyChecking=no",
        str(local_path),
        f"{args.ssh_host}:{remote_tmp}",
    ]
    rc = subprocess.run(scp_cmd).returncode
    if rc != 0:
        print(f"sync failed scp rc={rc}")
        return rc

    ssh_cmd = [
        "ssh",
        "-i",
        args.ssh_key,
        "-o",
        "ConnectTimeout=12",
        "-o",
        "StrictHostKeyChecking=no",
        args.ssh_host,
        f"mkdir -p {remote_dir} && mv {remote_tmp} {remote_file} && chown www-data:www-data {remote_file}",
    ]
    rc = subprocess.run(ssh_cmd).returncode
    if rc != 0:
        print(f"sync failed ssh rc={rc}")
        return rc

    print(f"synced brockler={len(brockler)} vacant={len(vacant)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
