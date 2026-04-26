#!/usr/bin/env python3
"""
Push Brockler case data to the live admin panel.

Scans all scraped JSON files in out/{year}/ and:
  1. Finds cases where Aaron Brockler is listed as defense attorney.
  2. Finds recently filed cases (default: last 90 days) with no defense attorney.
  3. Packages everything as cases_data.json and POSTs to /cases-sync.

Usage:
    python3 scripts/push_brockler_cases.py
    python3 scripts/push_brockler_cases.py --days 30 --host https://prosecutordefense.com

Env vars:
    BROCKLER_API_TOKEN   – plaintext admin password (same as admin UI login)
    CASES_PUSH_HOST      – override target host (default: https://prosecutordefense.com)
"""

import argparse
import csv
import glob
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib import request as urllib_request, error as urllib_error

# ── defaults ─────────────────────────────────────────────────────────────────
DEFAULT_HOST    = os.environ.get("CASES_PUSH_HOST", "https://prosecutordefense.com")
BROCKLER_NAMES  = {"BROCKLER", "AARON BROCKLER", "BROCKLER LAW"}
OVI_KEYWORDS    = [
    "OVI", "DUI", "IMPAIRED", "REFUSAL", "PHYSICAL CONTROL",
    "ALCOHOL", "BREATHALYZER", "CHEMICAL TEST", "INTOXICATED", "DRUNK DRIVING",
]
RECENT_DAYS_DEFAULT = 365
OUT_DIR         = os.path.join(os.path.dirname(__file__), "..", "out")


def _is_brockler(name: str) -> bool:
    n = (name or "").upper().strip()
    return any(b in n for b in BROCKLER_NAMES)


def _is_ovi(desc: str) -> bool:
    u = (desc or "").upper()
    return any(k in u for k in OVI_KEYWORDS)


def _parse_charges(summary: dict) -> list[dict]:
    """Extract charges list from the embedded_table_0 CSV in summary.fields."""
    fields = summary.get("fields", {})
    table = fields.get("embedded_table_0", {})
    if not isinstance(table, dict):
        return []
    raw_csv = table.get("data", "")
    if not raw_csv:
        return []
    charges = []
    try:
        reader = csv.DictReader(io.StringIO(raw_csv))
        for row in reader:
            ch = {
                "type":        (row.get("Type") or "").strip(),
                "statute":     (row.get("Statute") or "").strip(),
                "description": (row.get("Charge Description") or "").strip(),
                "disposition": (row.get("Disposition") or "").strip(),
            }
            if ch["type"] or ch["statute"] or ch["description"]:
                charges.append(ch)
    except Exception:
        pass
    return charges


def _flags(charges: list[dict], next_event: str, has_attorney: bool) -> list[dict]:
    flags = []
    if not has_attorney:
        flags.append({"label": "VACANT", "type": "flag-vacant"})
    ovi_hit = any(_is_ovi(c.get("description", "")) for c in charges)
    if ovi_hit:
        flags.append({"label": "OVI/DUI", "type": "flag-ovi"})
    if next_event:
        days = _days_until(next_event)
        if days is not None and 0 <= days <= 7:
            flags.append({"label": f"EVENT IN {days}d", "type": "flag-urgent"})
    return flags


def _days_until(date_str: str):
    """Parse MM/DD/YYYY format, return days from today."""
    if not date_str:
        return None
    parts = date_str.split("/")
    if len(parts) != 3:
        return None
    try:
        d = datetime(int(parts[2]), int(parts[0]), int(parts[1]))
        return (d - datetime.now()).days
    except (ValueError, IndexError):
        return None


def _indict_type(charges: list[dict]) -> str:
    """Return INDICT / TRUE BILL / BINDOVER based on charge types."""
    types = {c.get("type", "").upper() for c in charges}
    if "BINDOVER" in types:
        return "BINDOVER"
    if "TRUE BILL" in types or "TRUEBILL" in types:
        return "TRUE BILL"
    if "INDICT" in types:
        return "INDICT"
    return "/".join(sorted(t for t in types if t)) or "—"


def process_file(path: str) -> dict | None:
    """Load a JSON file and return a normalised case dict, or None if invalid."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None

    metadata = data.get("metadata", {})
    if not metadata.get("exists", True):
        return None

    summary  = data.get("summary", {})
    fields   = summary.get("fields", {})
    attorneys = data.get("attorneys", [])

    case_id  = metadata.get("case_id") or summary.get("case_id", "")
    if not case_id:
        return None

    # ── defendant ───────────────────────────────────────────────────────
    defendant_name = (fields.get("Name:") or "").strip()
    dob            = (fields.get("Date of Birth:") or "").strip()
    race           = (fields.get("Race:") or "").strip()
    sex            = (fields.get("Sex:") or "").strip()

    # ── attorneys ───────────────────────────────────────────────────────
    defense_atty = None
    is_brockler  = False
    for a in attorneys:
        party = (a.get("party") or "").upper()
        if party == "DEFENSE":
            name = (a.get("name") or "").strip()
            if _is_brockler(name):
                is_brockler  = True
                defense_atty = name
                break
            if defense_atty is None:
                defense_atty = name

    # ── charges ─────────────────────────────────────────────────────────
    charges    = _parse_charges(summary)
    indict_typ = _indict_type(charges)

    # ── case metadata ───────────────────────────────────────────────────
    status      = (fields.get("Status:") or "").strip()
    judge       = (fields.get("Judge Name:") or "").strip()
    next_event  = (fields.get("Next Event:") or "").strip()
    scraped_at  = metadata.get("scraped_at", "")

    case_obj = {
        "case_id":          case_id,
        "defendant_name":   defendant_name,
        "dob":              dob,
        "race":             race,
        "sex":              sex,
        "status":           status,
        "judge":            judge,
        "next_event":       next_event,
        "charges":          charges,
        "indict_type":      indict_typ,
        "defense_attorney": defense_atty,
        "is_brockler":      is_brockler,
        "scraped_at":       scraped_at,
        "flags":            [],   # populated below
    }
    case_obj["flags"] = _flags(charges, next_event, defense_atty is not None)
    return case_obj


def collect_cases(days: int) -> tuple[list[dict], list[dict]]:
    # For vacant cases, filter by case year (derived from case_id) rather than scraped_at.
    # --days controls how far back: e.g. 365 days → cases filed in 2024 or later.
    min_case_year = (datetime.now(tz=timezone.utc) - timedelta(days=days)).year
    brockler_cases: list[dict] = []
    vacant_cases:   list[dict] = []

    pattern = os.path.join(OUT_DIR, "*", "*.json")
    files   = sorted(glob.glob(pattern), reverse=True)  # newest file first — ensures latest scrape wins dedup
    seen_ids: set[str] = set()

    for path in files:
        c = process_file(path)
        if c is None:
            continue
        cid = c["case_id"]
        if cid in seen_ids:
            continue
        seen_ids.add(cid)

        if c["is_brockler"]:
            brockler_cases.append(c)
            continue

        # vacant / recent filings — filter by case year from case_id (e.g. CR-25-NNNNNN-A → 2025)
        if not c["defense_attorney"]:
            cid = c.get("case_id", "")
            try:
                parts = cid.split("-")
                raw = parts[1] if len(parts) >= 2 else ""
                case_year = int(raw) + 2000 if len(raw) == 2 else int(raw)
                if case_year < min_case_year:
                    continue
            except (ValueError, IndexError, AttributeError):
                pass
            vacant_cases.append(c)

    # sort: brockler by case number desc (highest/newest first), vacant by scraped_at newest first
    def _case_num(x):
        """Extract numeric portion from case_id like CR-25-706402-A → 706402."""
        try:
            return int(x.get("case_id", "").split("-")[2])
        except (IndexError, ValueError):
            return 0

    brockler_cases.sort(key=_case_num, reverse=True)
    vacant_cases.sort(key=lambda x: x.get("scraped_at", ""), reverse=True)

    return brockler_cases, vacant_cases


def push(host: str, token: str, brockler: list, vacant: list) -> None:
    url  = host.rstrip("/") + "/cases-sync"
    body = json.dumps({
        "token": token,
        "data":  {
            "brockler_cases": brockler,
            "vacant_cases":   vacant,
        }
    }).encode("utf-8")

    req = urllib_request.Request(
        url,
        data    = body,
        method  = "POST",
        headers = {"Content-Type": "application/json"},
    )
    try:
        with urllib_request.urlopen(req, timeout=30) as resp:
            result = json.load(resp)
            if result.get("ok"):
                print(f"✓ Synced {len(brockler)} Brockler cases + {len(vacant)} vacant → {result.get('synced_at','')}")
            else:
                print(f"✗ API error: {result}", file=sys.stderr)
                sys.exit(1)
    except urllib_error.HTTPError as exc:
        msg = exc.read().decode("utf-8", errors="replace")
        print(f"✗ HTTP {exc.code}: {msg}", file=sys.stderr)
        sys.exit(1)
    except urllib_error.URLError as exc:
        print(f"✗ Network error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Push Brockler case data to admin panel.")
    parser.add_argument("--days", type=int, default=RECENT_DAYS_DEFAULT,
                        help="How many days back to include vacant filings (default: 90)")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="Target host (default: https://prosecutordefense.com)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary without pushing to VPS")
    args = parser.parse_args()

    token = os.environ.get("BROCKLER_API_TOKEN", "").strip()
    if not token and not args.dry_run:
        print("Error: set BROCKLER_API_TOKEN env var to your admin password.", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {OUT_DIR} …")
    brockler, vacant = collect_cases(args.days)
    print(f"  Brockler cases : {len(brockler)}")
    print(f"  Vacant (≤{args.days}d): {len(vacant)}")

    if args.dry_run:
        print("\n── Dry run ── first 3 Brockler cases ──")
        for c in brockler[:3]:
            print(json.dumps(c, indent=2))
        print("\n── first 3 vacant cases ──")
        for c in vacant[:3]:
            print(json.dumps(c, indent=2))
        return

    push(args.host, token, brockler, vacant)


if __name__ == "__main__":
    main()
