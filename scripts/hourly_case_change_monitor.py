#!/usr/bin/env python3
"""
Business-hour case change monitor for user-tracked cases.

What it does:
1. Re-scrapes each case from my_cases.json.
2. Compares latest snapshot against previous state.
3. Sends notifications when meaningful fields change.

Notification channels (optional, env-driven):
- Email: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM, EMAIL_TO
- SMS (Twilio): TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, TWILIO_TO
- In-app webhook: IN_APP_WEBHOOK_URL
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import smtplib
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / "state"
OUT_DIR = REPO_ROOT / "out"
STATE_FILE = STATE_DIR / "hourly_case_monitor_state.json"
LOG_FILE = STATE_DIR / "hourly_case_monitor.log"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def log(msg: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{now_iso()} {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


@dataclass
class CaseConfig:
    case_id: str
    year: int
    number: int


def load_cases(path: Path) -> List[CaseConfig]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("cases", [])
    cases: List[CaseConfig] = []
    for item in items:
        try:
            cases.append(
                CaseConfig(
                    case_id=str(item["case_id"]),
                    year=int(item["year"]),
                    number=int(item["number"]),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    return cases


def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {"cases": {}}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("cases"), dict):
            return data
    except Exception:
        pass
    return {"cases": {}}


def save_state(state: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def scrape_case(case: CaseConfig, delay_ms: int) -> int:
    cmd = [
        sys.executable,
        "main.py",
        "scrape",
        "--year",
        str(case.year),
        "--start",
        str(case.number),
        "--limit",
        "1",
        "--direction",
        "up",
        "--headless",
        "--delay-ms",
        str(delay_ms),
    ]
    log(f"scrape start {case.case_id} (delay_ms={delay_ms})")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    log(f"scrape end {case.case_id} rc={result.returncode}")
    return result.returncode


def latest_case_file(case: CaseConfig) -> Optional[Path]:
    year_dir = OUT_DIR / str(case.year)
    if not year_dir.exists():
        return None
    prefix = f"{case.year}-{case.number}_"
    files = sorted([p for p in year_dir.glob(prefix + "*.json") if p.is_file()])
    return files[-1] if files else None


def summarize_case(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("metadata", {})
    summary = data.get("summary", {})
    fields = summary.get("fields", {})
    charges = summary.get("charges", [])
    attorneys = data.get("attorneys", [])

    payload = {
        "file": path.name,
        "scraped_at": meta.get("scraped_at") or "",
        "case_id": meta.get("case_id") or summary.get("case_id") or "",
        "status": fields.get("Status:") or "",
        "next_event": fields.get("Next Event:") or "",
        "judge": fields.get("Judge Name:") or "",
        "charges": charges,
        "attorneys": attorneys,
    }

    fp_material = {
        "status": payload["status"],
        "next_event": payload["next_event"],
        "judge": payload["judge"],
        "charges": payload["charges"],
        "attorneys": payload["attorneys"],
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(fp_material, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return payload


def diff_summary(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    changed: Dict[str, Any] = {}
    for key in ["status", "next_event", "judge"]:
        if old.get(key) != new.get(key):
            changed[key] = {"from": old.get(key), "to": new.get(key)}

    old_charges = old.get("charges", [])
    new_charges = new.get("charges", [])
    if old_charges != new_charges:
        changed["charges"] = {
            "from_count": len(old_charges),
            "to_count": len(new_charges),
        }

    old_attys = old.get("attorneys", [])
    new_attys = new.get("attorneys", [])
    if old_attys != new_attys:
        changed["attorneys"] = {
            "from_count": len(old_attys),
            "to_count": len(new_attys),
        }

    return changed


def send_email(subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")
    sender = os.getenv("EMAIL_FROM", user)
    recipient = os.getenv("EMAIL_TO", "")

    if not (host and sender and recipient):
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        log(f"email send failed: {exc}")
        return False


def send_twilio_sms(message: str) -> bool:
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_num = os.getenv("TWILIO_FROM", "")
    to_num = os.getenv("TWILIO_TO", "")

    if not (sid and token and from_num and to_num):
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urllib.parse.urlencode({"From": from_num, "To": to_num, "Body": message}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    basic = (sid + ":" + token).encode("utf-8")
    auth = "Basic " + __import__("base64").b64encode(basic).decode("ascii")
    req.add_header("Authorization", auth)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:
        log(f"sms send failed: {exc}")
        return False


def send_in_app(payload: Dict[str, Any]) -> bool:
    webhook = os.getenv("IN_APP_WEBHOOK_URL", "")
    if not webhook:
        return False

    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(webhook, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:
        log(f"in-app webhook failed: {exc}")
        return False


def notify(case_id: str, diff: Dict[str, Any], latest: Dict[str, Any]) -> None:
    subject = f"Case change detected: {case_id}"
    body = (
        f"Case: {case_id}\n"
        f"When: {now_iso()}\n"
        f"Latest snapshot: {latest.get('file')}\n"
        f"Scraped at: {latest.get('scraped_at')}\n"
        f"\nChanges:\n{json.dumps(diff, indent=2)}\n"
    )

    email_ok = send_email(subject, body)
    sms_text = f"{case_id} changed. Status={latest.get('status') or 'N/A'}, Next={latest.get('next_event') or 'N/A'}"
    sms_ok = send_twilio_sms(sms_text)
    app_ok = send_in_app(
        {
            "type": "case_change",
            "case_id": case_id,
            "at": now_iso(),
            "latest": {
                "file": latest.get("file"),
                "scraped_at": latest.get("scraped_at"),
                "status": latest.get("status"),
                "next_event": latest.get("next_event"),
                "judge": latest.get("judge"),
            },
            "diff": diff,
        }
    )

    log(
        "notify "
        + case_id
        + f" email={'ok' if email_ok else 'skip/fail'} sms={'ok' if sms_ok else 'skip/fail'} in_app={'ok' if app_ok else 'skip/fail'}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Hourly monitor for tracked cases")
    parser.add_argument("--cases-file", default="my_cases.json")
    parser.add_argument("--delay-ms", type=int, default=2000)
    parser.add_argument("--skip-scrape", action="store_true", help="Only compare latest local snapshots")
    args = parser.parse_args()

    cases_path = (REPO_ROOT / args.cases_file).resolve()
    cases = load_cases(cases_path)
    if not cases:
        log("no cases configured")
        return 1

    state = load_state()
    state_cases = state.setdefault("cases", {})

    for case in cases:
        if not args.skip_scrape:
            scrape_case(case, args.delay_ms)

        latest_path = latest_case_file(case)
        if not latest_path:
            log(f"{case.case_id}: no snapshot found")
            continue

        latest = summarize_case(latest_path)
        old = state_cases.get(case.case_id)

        if not old:
            state_cases[case.case_id] = latest
            log(f"{case.case_id}: baseline set -> {latest['file']}")
            continue

        if old.get("fingerprint") != latest.get("fingerprint"):
            diff = diff_summary(old, latest)
            log(f"{case.case_id}: CHANGE detected -> {latest['file']} diff_keys={','.join(diff.keys()) or 'content'}")
            notify(case.case_id, diff, latest)
            state_cases[case.case_id] = latest
        else:
            log(f"{case.case_id}: no change ({latest['file']})")

    state["last_run"] = now_iso()
    save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
