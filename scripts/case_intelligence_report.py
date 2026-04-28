#!/usr/bin/env python3
"""
Case Intelligence Report
========================
Generates three CSV reports from all scraped case JSONs:

1. nightmare_cases.csv
   - Cases with docket events like bench warrants, FTA, capias, revocation
   - Includes defendant name, address, case number, nightmare events

2. clean_cases_attorneys.csv
   - Cases with no nightmare docket events + a defense attorney on record
   - Useful for identifying successful defense representation patterns

3. multi_case_defendants.csv
   - Defendants with multiple known cases (Other Cases field)
   - Shows all case outcomes and defense attorneys across their history

Usage:
    python3 scripts/case_intelligence_report.py
    python3 scripts/case_intelligence_report.py --years 2023 2024 2025 2026
    python3 scripts/case_intelligence_report.py --out-dir /path/to/reports
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- #
# Nightmare keyword patterns (case-insensitive, match anywhere in description) #
# --------------------------------------------------------------------------- #
NIGHTMARE_PATTERNS = [
    r"BENCH WARRANT",
    r"CAPIAS",
    r"FAILURE TO APPEAR",
    r"\bFTA\b",
    r"BOND FORFEITURE",
    r"BOND REVOKED",
    r"BOND REVOCATION",
    r"REVOCATION HEARING",
    r"PROBATION REVOCATION",
    r"COMMUNITY CONTROL VIOLATION",
    r"SHOW CAUSE",
    r"CONTEMPT",
    r"FUGITIVE",
    r"MISSED",
    r"WARRANT ISSUED",
    r"WARRANT RETURNED",
]

_NIGHTMARE_RE = re.compile(
    "|".join(NIGHTMARE_PATTERNS), re.IGNORECASE
)


def is_nightmare_event(description: str) -> bool:
    return bool(_NIGHTMARE_RE.search(description or ""))


# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #

def latest_json_per_case(year_dirs) -> dict:
    """Return {case_number: path_to_latest_json} across all year dirs."""
    cases = {}
    for yr_dir in year_dirs:
        for path in glob.glob(str(yr_dir / "*.json")):
            fname = os.path.basename(path)
            # filename: YYYY-NNNNNN_YYYYMMDD_HHMMSS.json
            m = re.match(r"(\d{4}-\d+)_(\d{8}_\d{6})\.json", fname)
            if not m:
                continue
            key = m.group(1)
            ts = m.group(2)
            existing = cases.get(key)
            if existing is None or ts > existing[1]:
                cases[key] = (path, ts)
    return {k: v[0] for k, v in cases.items()}


def load_case(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_defendant_info(data: dict) -> dict:
    """Extract name, DOB, address from defendant tab."""
    def_ = data.get("defendant", {})
    name = def_.get("Name:", "") or ""
    dob = def_.get("DOB:", "") or def_.get("Date of Birth:", "") or ""
    address = def_.get("Address:", "") or ""
    line2 = def_.get("Line 2:", "") or ""
    city_state_zip = def_.get("City, State, Zip:", "") or ""
    # Also check summary fields if defendant tab was empty
    if not name:
        sf = data.get("summary", {}).get("fields", {})
        name = sf.get("Name:", "") or ""
        dob = dob or sf.get("Date of Birth:", "") or ""
    full_address = ", ".join(p for p in [address, line2, city_state_zip] if p and p != "N/A")
    return {
        "name": name.strip(),
        "dob": dob.strip(),
        "address": full_address.strip(),
    }


def get_case_number(data: dict) -> str:
    meta = data.get("metadata", {})
    cn = meta.get("case_id") or meta.get("case_number") or ""
    if not cn:
        # Try summary
        sf = data.get("summary", {}).get("fields", {})
        cn = sf.get("Number:", "") or ""
        # Or from summary case_id
        cn = cn or data.get("summary", {}).get("case_id", "")
    return (cn or "").strip()


def get_case_status(data: dict) -> str:
    sf = data.get("summary", {}).get("fields", {})
    return sf.get("Status:", "").strip()


def get_charges_summary(data: dict) -> str:
    """Return a short CSV-safe charges string."""
    charges = data.get("charges", [])
    if charges:
        return "; ".join(
            c.get("description", c.get("charge_description", ""))
            for c in charges[:5]
        )
    # Try embedded table in summary
    sf = data.get("summary", {}).get("fields", {})
    et = sf.get("embedded_table_0", {})
    if isinstance(et, dict) and et.get("format") == "csv":
        lines = et.get("data", "").split("\r\n")[1:6]  # skip header
        descs = []
        for line in lines:
            parts = line.split(",")
            if len(parts) >= 3:
                descs.append(parts[2].strip())
        return "; ".join(d for d in descs if d)
    return ""


def get_defense_attorneys(data: dict) -> list:
    """Return list of {name, contact} dicts for defense attorneys."""
    attorneys = data.get("attorneys", [])
    result = []
    for a in attorneys:
        party = (a.get("party") or "").lower()
        if "defense" in party or "defendant" in party:
            result.append({
                "name": a.get("name", "").strip(),
                "contact": (a.get("contact") or "").replace("\n", " | ").strip(),
                "role": a.get("role", "").strip(),
                "type": a.get("type", "").strip(),
            })
    return result


def get_nightmare_events(data: dict) -> list:
    """Return list of docket descriptions that match nightmare patterns."""
    docket = data.get("docket", [])
    bad = []
    for entry in docket:
        desc = entry.get("description", "")
        if is_nightmare_event(desc):
            bad.append(f"{entry.get('proceeding_date','')} - {desc}")
    return bad


def get_other_cases(data: dict) -> list:
    """Return list of other case numbers for this defendant."""
    sf = data.get("summary", {}).get("fields", {})
    raw = sf.get("Other Cases:", "") or ""
    if not raw or raw.strip() == "N/A":
        return []
    return [c.strip() for c in raw.split(",") if c.strip() and c.strip() != "N/A"]


# --------------------------------------------------------------------------- #
# Main report builder                                                           #
# --------------------------------------------------------------------------- #

def build_reports(year_dirs, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Scanning case JSONs across {len(year_dirs)} year dir(s)...")
    case_map = latest_json_per_case(year_dirs)
    print(f"[*] Found {len(case_map):,} unique cases")

    nightmare_rows = []
    clean_attorney_rows = []
    # defendant_id → list of case info for multi-case report
    defendant_cases = defaultdict(list)  # keyed by normalized name+dob

    for case_key, path in sorted(case_map.items()):
        data = load_case(path)
        if not data:
            continue

        case_number = get_case_number(data) or case_key.replace("-", " ").strip()
        # Rebuild canonical case number from filename key (YYYY-NNNNNN → CR-YY-NNNNNN-A assumed)
        if not case_number:
            case_number = case_key

        status = get_case_status(data)
        def_info = get_defendant_info(data)
        defense_attorneys = get_defense_attorneys(data)
        nightmare_events = get_nightmare_events(data)
        other_cases = get_other_cases(data)
        charges_str = get_charges_summary(data)
        judge = data.get("summary", {}).get("fields", {}).get("Judge Name:", "").strip()

        atty_names = "; ".join(a["name"] for a in defense_attorneys) if defense_attorneys else ""
        atty_contacts = "; ".join(a["contact"] for a in defense_attorneys if a["contact"]) if defense_attorneys else ""

        # --- Nightmare report ---
        if nightmare_events:
            nightmare_rows.append({
                "case_number": case_number,
                "status": status,
                "defendant_name": def_info["name"],
                "dob": def_info["dob"],
                "address": def_info["address"],
                "charges": charges_str,
                "judge": judge,
                "nightmare_events": " | ".join(nightmare_events[:10]),
                "defense_attorney": atty_names,
                "attorney_contact": atty_contacts,
                "other_cases_count": len(other_cases),
            })

        # --- Clean cases with attorney ---
        if not nightmare_events and defense_attorneys:
            nightmare_rows  # already handled above
            clean_attorney_rows.append({
                "case_number": case_number,
                "status": status,
                "defendant_name": def_info["name"],
                "charges": charges_str,
                "judge": judge,
                "defense_attorney": atty_names,
                "attorney_contact": atty_contacts,
                "attorney_type": "; ".join(a["type"] for a in defense_attorneys),
                "other_cases_count": len(other_cases),
            })

        # --- Multi-case tracking ---
        if other_cases or len(other_cases) >= 0:
            # Track every defendant; filter to multi-case later
            ident_key = f"{def_info['name']}|{def_info['dob']}"
            if ident_key.startswith("|"):
                continue  # skip if no name
            defendant_cases[ident_key].append({
                "case_number": case_number,
                "status": status,
                "charges": charges_str,
                "judge": judge,
                "defense_attorney": atty_names,
                "attorney_contact": atty_contacts,
                "has_nightmare": bool(nightmare_events),
                "nightmare_events": " | ".join(nightmare_events[:5]),
                "other_cases_listed": ", ".join(other_cases[:10]),
            })

    # Build multi-case rows
    multi_case_rows = []
    for ident_key, case_list in defendant_cases.items():
        # Include if they have 2+ cases in our data OR their summary lists other cases
        has_listed_others = any(c["other_cases_listed"] for c in case_list)
        if len(case_list) < 2 and not has_listed_others:
            continue
        name, dob = ident_key.split("|", 1)
        for c in case_list:
            multi_case_rows.append({
                "defendant_name": name,
                "dob": dob,
                "total_cases_in_data": len(case_list),
                "other_cases_on_record": c["other_cases_listed"],
                "case_number": c["case_number"],
                "status": c["status"],
                "charges": c["charges"],
                "judge": c["judge"],
                "defense_attorney": c["defense_attorney"],
                "attorney_contact": c["attorney_contact"],
                "has_nightmare_events": c["has_nightmare"],
                "nightmare_events": c["nightmare_events"],
            })

    # --- Write CSVs ---
    def write_csv(rows, filename, fieldnames):
        fpath = out_dir / filename
        with open(fpath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[+] {filename}: {len(rows):,} rows → {fpath}")

    write_csv(
        nightmare_rows,
        "nightmare_cases.csv",
        ["case_number", "status", "defendant_name", "dob", "address",
         "charges", "judge", "nightmare_events", "defense_attorney",
         "attorney_contact", "other_cases_count"],
    )

    write_csv(
        clean_attorney_rows,
        "clean_cases_attorneys.csv",
        ["case_number", "status", "defendant_name", "charges", "judge",
         "defense_attorney", "attorney_contact", "attorney_type", "other_cases_count"],
    )

    write_csv(
        multi_case_rows,
        "multi_case_defendants.csv",
        ["defendant_name", "dob", "total_cases_in_data", "other_cases_on_record",
         "case_number", "status", "charges", "judge", "defense_attorney",
         "attorney_contact", "has_nightmare_events", "nightmare_events"],
    )

    print(f"\n[*] Done. Reports saved to: {out_dir}")
    print(f"    nightmare_cases.csv      : {len(nightmare_rows):,} cases with problems")
    print(f"    clean_cases_attorneys.csv: {len(clean_attorney_rows):,} clean cases with attorney")
    print(f"    multi_case_defendants.csv: {len(multi_case_rows):,} rows for repeat defendants")


def main():
    parser = argparse.ArgumentParser(description="Case Intelligence Report Generator")
    parser.add_argument(
        "--years", nargs="+", type=int,
        default=[2023, 2024, 2025, 2026],
        help="Years to include (default: 2023 2024 2025 2026)",
    )
    parser.add_argument(
        "--out-dir", default=str(REPO_ROOT / "reports"),
        help="Output directory for CSVs (default: ./reports)",
    )
    parser.add_argument(
        "--out-root", default=str(REPO_ROOT / "out"),
        help="Root directory containing year subdirs (default: ./out)",
    )
    args = parser.parse_args()

    out_root = Path(args.out_root)
    year_dirs = []
    for yr in args.years:
        d = out_root / str(yr)
        if d.exists():
            year_dirs.append(d)
        else:
            print(f"[!] Year dir not found, skipping: {d}")

    if not year_dirs:
        print("[!] No valid year directories found. Exiting.")
        sys.exit(1)

    build_reports(year_dirs, Path(args.out_dir))


if __name__ == "__main__":
    main()
