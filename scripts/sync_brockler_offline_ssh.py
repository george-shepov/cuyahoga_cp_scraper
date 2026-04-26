#!/usr/bin/env python3
"""
Sync only Brockler cases (latest JSON + case PDF folders) to node186 for offline access.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

from push_brockler_cases import collect_cases


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "out"
CASE_RE = re.compile(r"^CR-(\d{2})-(\d{6})-[A-Z]$")
JSON_RE = re.compile(r"^(\d{4})-(\d{6})_(\d{8}_\d{6})\.json$")


def latest_json_for_case(case_id: str) -> Path | None:
    m = CASE_RE.match(case_id)
    if not m:
        return None
    yy = int(m.group(1))
    num = m.group(2)
    year = 2000 + yy
    year_dir = OUT_ROOT / str(year)
    if not year_dir.exists():
        return None

    best: tuple[str, Path] | None = None
    for p in year_dir.glob(f"{year}-{num}_*.json"):
        mm = JSON_RE.match(p.name)
        if not mm:
            continue
        ts = mm.group(3)
        if best is None or ts > best[0]:
            best = (ts, p)
    return best[1] if best else None


def run(cmd: list[str]) -> int:
    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync Brockler-only JSON/PDF cache to SSH node")
    ap.add_argument("--ssh-host", default="root@104.237.2.186")
    ap.add_argument("--ssh-key", default=str(Path.home() / ".ssh" / "vps_dime_key"))
    ap.add_argument("--remote-root", default="/opt/brockler-node/brockler-only")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    brockler, _vacant = collect_cases(days=36500)
    case_ids = sorted({c.get("case_id", "") for c in brockler if c.get("case_id")})

    if not case_ids:
        print("[offline-sync] no brockler cases found")
        return 0

    remote_root = args.remote_root.rstrip("/")
    remote_json_root = f"{remote_root}/json"
    remote_pdf_root = f"{remote_root}/pdfs"

    mkdir_cmd = [
        "ssh",
        "-i",
        args.ssh_key,
        "-o",
        "StrictHostKeyChecking=no",
        args.ssh_host,
        f"mkdir -p '{remote_json_root}' '{remote_pdf_root}'",
    ]
    if not args.dry_run and run(mkdir_cmd) != 0:
        print("[offline-sync] failed creating remote directories")
        return 1

    json_synced = 0
    pdf_synced = 0

    for cid in case_ids:
        p = latest_json_for_case(cid)
        if p is not None:
            rel_year = p.parent.name
            scp_cmd = [
                "scp",
                "-i",
                args.ssh_key,
                "-o",
                "ConnectTimeout=12",
                "-o",
                "StrictHostKeyChecking=no",
                str(p),
                f"{args.ssh_host}:{remote_json_root}/{rel_year}_{p.name}",
            ]
            if args.dry_run:
                print("[offline-sync] DRY", " ".join(scp_cmd))
            elif run(scp_cmd) == 0:
                json_synced += 1

        m = CASE_RE.match(cid)
        if not m:
            continue
        year = str(2000 + int(m.group(1)))
        pdf_dir = OUT_ROOT / year / "pdfs" / cid
        if pdf_dir.exists():
            rsync_cmd = [
                "rsync",
                "-az",
                "--delete",
                "-e",
                f"ssh -i {args.ssh_key} -o StrictHostKeyChecking=no",
                str(pdf_dir) + "/",
                f"{args.ssh_host}:{remote_pdf_root}/{cid}/",
            ]
            if args.dry_run:
                print("[offline-sync] DRY", " ".join(rsync_cmd))
            elif run(rsync_cmd) == 0:
                pdf_synced += 1

    print(f"[offline-sync] brockler_cases={len(case_ids)} json_synced={json_synced} pdf_dirs_synced={pdf_synced}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
