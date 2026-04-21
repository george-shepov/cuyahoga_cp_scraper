#!/usr/bin/env python3
"""
Fetch Ohio Supreme Court attorney data for all attorneys in attorneys_analysis.csv.
Outputs docs/foxxiie/data.json with judges, prosecutors, and attorneys enriched
with their Supreme Court profile data (status, admission date, employer, law school).

Usage:
    python3 scripts/fetch_sc_attorneys.py

Rate-limits itself to ~1 request/sec to be polite to the Supreme Court server.
Run this whenever you want to refresh the data (e.g., monthly).
"""

import csv
import json
import re
import time
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "foxxiie"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SC_BASE = "https://www.supremecourt.ohio.gov/AttorneySearch/"
SC_AJAX = "https://www.supremecourt.ohio.gov/AttorneySearch/Ajax.ashx"

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Referer": SC_BASE,
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
}

# ── session setup ────────────────────────────────────────────────────────────

def _make_session():
    """Create a urllib opener with a cookie jar and fetch CSRF token."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    resp = opener.open(SC_BASE, timeout=15)
    html = resp.read().decode("utf-8")
    m = re.search(r'name="csrf-token"[^>]*content="([^"]+)"', html)
    csrf = m.group(1) if m else ""
    return opener, csrf


def _post(opener, csrf, fields: dict) -> dict | list | None:
    data = urllib.parse.urlencode(fields).encode()
    headers = dict(HEADERS_BASE)
    headers["X-CSRF-TOKEN"] = csrf
    req = urllib.request.Request(SC_AJAX, data=data, headers=headers)
    try:
        r = opener.open(req, timeout=15)
        body = r.read().decode("utf-8")
        if not body.strip() or body.strip() == "No Data":
            return None
        return json.loads(body)
    except Exception:
        return None


# ── search + detail ──────────────────────────────────────────────────────────

def search_by_name(opener, csrf, last: str, first: str) -> list[dict]:
    """Return list of search hits (may be multiple matches)."""
    result = _post(opener, csrf, {
        "action": "SearchAttorney",
        "firstName": first.strip().split()[0] if first.strip() else "",
        "lastName": last.strip().split(",")[0].strip(),
        "middleName": "",
        "attyReg": "",
        "address": "",
        "city": "",
        "state": "",
        "county": "",
    })
    if not result or not isinstance(result, dict):
        return []
    return result.get("MySearchResults") or []


def get_detail(opener, csrf, reg_number: int) -> dict | None:
    """Fetch full attorney profile by registration number."""
    return _post(opener, csrf, {
        "action": "GetAttyInfo",
        "regNumber": str(reg_number),
    })


def get_discipline(opener, csrf, atty_number: int) -> list[dict]:
    result = _post(opener, csrf, {
        "action": "GetAttyDiscipline",
        "attyNumber": str(atty_number),
    })
    if isinstance(result, list):
        return result
    return []


# ── parse name "LAST, FIRST" ─────────────────────────────────────────────────

def split_name(name: str) -> tuple[str, str]:
    """Split 'DOE, JOHN' → ('DOE', 'JOHN'). Falls back gracefully."""
    parts = name.split(",", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    tokens = name.strip().split()
    if len(tokens) >= 2:
        return tokens[-1], tokens[0]
    return name.strip(), ""


# ── read CSVs ────────────────────────────────────────────────────────────────

def read_csv(path: Path, required_col: str) -> list[dict]:
    rows = []
    if not path.exists():
        print(f"  WARN: {path} not found")
        return rows
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if required_col in row:
                rows.append(dict(row))
    return rows


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Loading CSVs...")
    atty_rows = read_csv(ROOT / "attorneys_analysis.csv", "Attorney Name")
    judge_rows = read_csv(ROOT / "judges_analysis.csv", "Judge Name")
    pros_rows = read_csv(ROOT / "prosecutors_analysis.csv", "Prosecutor Name")

    print(f"  {len(atty_rows)} attorneys, {len(judge_rows)} judges, {len(pros_rows)} prosecutors")

    # Check for existing cache to avoid re-fetching
    cache_path = OUT_DIR / "sc_cache.json"
    cache: dict = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text())
        print(f"  Loaded {len(cache)} cached SC records")

    print("\nInitialising Supreme Court session...")
    opener, csrf = _make_session()
    print(f"  Session ready. CSRF: {csrf[:20]}...")

    print("\nFetching SC data for attorneys (this takes a few minutes)...")
    enriched_attys = []
    needs_save = False

    for i, row in enumerate(atty_rows, 1):
        name = row.get("Attorney Name", "").strip()
        if not name or name == "N/A":
            continue

        cache_key = name.upper()

        if cache_key not in cache:
            last, first = split_name(name)
            hits = search_by_name(opener, csrf, last, first)
            time.sleep(0.6)  # polite rate limit

            sc_data = None
            if hits:
                # Take first hit (usually exact match)
                hit = hits[0]
                reg = hit.get("AttorneyNumber")
                if reg:
                    detail = get_detail(opener, csrf, reg)
                    time.sleep(0.4)
                    if detail and isinstance(detail, dict) and detail.get("FormalName"):
                        sc_data = {
                            "reg_number": reg,
                            "formal_name": detail.get("FormalName", ""),
                            "status": detail.get("Status", ""),
                            "employer": detail.get("Employer", ""),
                            "job_title": detail.get("JobTitle", ""),
                            "law_school": detail.get("LawSchool", ""),
                            "admitted_by": detail.get("AdmittedBy", ""),
                            "admission_date": detail.get("AdmissionDate", ""),
                            "city": detail.get("City", ""),
                            "state": detail.get("State", ""),
                            "has_discipline": detail.get("HasDiscipline", "NO"),
                        }

            cache[cache_key] = sc_data or {}
            needs_save = True

            if i % 20 == 0:
                cache_path.write_text(json.dumps(cache, indent=2))
                print(f"  {i}/{len(atty_rows)} — saved cache")
            else:
                print(f"  {i}/{len(atty_rows)} {name[:40]:<40} → {'FOUND' if sc_data else 'not found'}")

        sc = cache.get(cache_key) or {}
        atty = {
            "name": name,
            "cases": int(row.get("Number of Cases", 0) or 0),
            "guilty": int(row.get("Guilty", 0) or 0),
            "not_guilty": int(row.get("Not Guilty", 0) or 0),
            "dismissed": int(row.get("Dismissed", 0) or 0),
            "success_rate": row.get("Success Rate", "").strip(),
        }
        if sc:
            atty.update(sc)
        enriched_attys.append(atty)

    if needs_save:
        cache_path.write_text(json.dumps(cache, indent=2))
        print(f"\nCache saved to {cache_path}")

    # Build judges list
    judges = []
    for row in judge_rows:
        name = row.get("Judge Name", "").strip()
        if not name or name == "N/A":
            continue
        judges.append({
            "name": name,
            "cases": int(row.get("Number of Cases", 0) or 0),
            "patterns": row.get("Notable Patterns", "").strip(),
        })

    # Build prosecutors list
    prosecutors = []
    for row in pros_rows:
        name = row.get("Prosecutor Name", "").strip()
        if not name or name == "N/A":
            continue
        prosecutors.append({
            "name": name,
            "cases": int(row.get("Number of Cases", 0) or 0),
            "guilty": int(row.get("Guilty", 0) or 0),
            "not_guilty": int(row.get("Not Guilty", 0) or 0),
            "dismissed": int(row.get("Dismissed", 0) or 0),
            "conviction_rate": row.get("Conviction Rate", "").strip(),
        })

    # Sort by case count descending
    enriched_attys.sort(key=lambda x: -x["cases"])
    judges.sort(key=lambda x: -x["cases"])
    prosecutors.sort(key=lambda x: -x["cases"])

    output = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "judges": judges,
        "attorneys": enriched_attys,
        "prosecutors": prosecutors,
    }

    out_path = OUT_DIR / "data.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path}")
    print(f"  Judges:      {len(judges)}")
    print(f"  Attorneys:   {len(enriched_attys)}")
    print(f"  Prosecutors: {len(prosecutors)}")
    print(f"\nNext: open docs/foxxiie/index.html in a browser to preview.")


if __name__ == "__main__":
    main()
