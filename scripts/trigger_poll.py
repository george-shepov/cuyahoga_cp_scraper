#!/usr/bin/env python3
"""
Trigger poll — runs every 5 minutes via cron on the .52 scraping node.

Checks /opt/brocklerlaw-save/scrape_trigger.json on .186 over SSH.
If a refresh has been requested from the admin panel:
  1. Clears the trigger on .186.
  2. Runs a current-year forward scrape (new 2026 cases).
  3. Pushes updated brockler+vacant payload to .186.

Usage (cron on .52):
  */5 * * * * cd /home/shepov/brockler-scraper && /home/shepov/brockler-scraper/.venv/bin/python3 scripts/trigger_poll.py >> logs/trigger_poll.log 2>&1
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT   = Path(__file__).resolve().parents[1]
PYTHON      = sys.executable
LOGS_DIR    = REPO_ROOT / "logs"
SSH_HOST    = "root@104.237.2.186"
SSH_KEY     = str(Path.home() / ".ssh" / "id_ed25519")
TRIGGER_FILE = "/opt/brocklerlaw-save/scrape_trigger.json"
CASES_FILE  = "/opt/brocklerlaw-save/cases_data.json"

# How many new case numbers to check ahead when triggered
TRIGGER_FORWARD_LIMIT = 200


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def log(msg: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{now_iso()} {msg}"
    print(line, flush=True)


def ssh_read_json(remote_path: str) -> dict:
    """Read a JSON file from .186 via SSH."""
    result = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "ConnectTimeout=10",
         "-o", "StrictHostKeyChecking=no", SSH_HOST,
         f"cat {remote_path} 2>/dev/null || echo '{{}}'"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        return {}
    try:
        return json.loads(result.stdout.strip())
    except (json.JSONDecodeError, ValueError):
        return {}


def ssh_clear_trigger() -> bool:
    """Clear the trigger flag on .186."""
    clear_payload = json.dumps({"requested": False, "cleared_at": now_iso()})
    result = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "ConnectTimeout=10",
         "-o", "StrictHostKeyChecking=no", SSH_HOST,
         f"echo '{clear_payload}' > {TRIGGER_FILE}.tmp && mv {TRIGGER_FILE}.tmp {TRIGGER_FILE}"],
        capture_output=True, text=True, timeout=15,
    )
    return result.returncode == 0


def run_forward_scrape() -> int:
    """Run a forward scrape for current year to pick up new cases."""
    from datetime import datetime as dt
    current_year = dt.now().year
    cmd = [
        PYTHON, "main.py", "scrape",
        "--year", str(current_year),
        "--direction", "up",
        "--limit", str(TRIGGER_FORWARD_LIMIT),
        "--headless",
        "--delay-ms", "2000",
        "--download-pdfs",
        "--pdf-types", "CR",
    ]
    log(f"trigger: running forward scrape year={current_year} limit={TRIGGER_FORWARD_LIMIT}")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return result.returncode


def run_push() -> int:
    """Push updated case data to .186."""
    cmd = [
        PYTHON, "scripts/sync_cases_payload_ssh.py",
        "--days", "36500",
        "--ssh-host", SSH_HOST,
        "--ssh-key", SSH_KEY,
        "--remote-cases-file", CASES_FILE,
    ]
    log("trigger: pushing updated case payload to .186")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return result.returncode


def main() -> None:
    trigger = ssh_read_json(TRIGGER_FILE)

    if not trigger.get("requested"):
        # No trigger — nothing to do, exit silently
        return

    requested_at = trigger.get("requested_at", "unknown")
    log(f"trigger: FIRE — requested_at={requested_at}")

    # Clear first so a second poll doesn't double-fire
    if not ssh_clear_trigger():
        log("trigger: WARNING — could not clear trigger on .186, aborting to avoid duplicate scrape")
        return

    rc = run_forward_scrape()
    if rc != 0:
        log(f"trigger: scrape exited with code {rc}")
    else:
        log("trigger: scrape completed OK")

    rc2 = run_push()
    if rc2 != 0:
        log(f"trigger: push exited with code {rc2}")
    else:
        log("trigger: push completed OK — cases updated on .186")


if __name__ == "__main__":
    main()
