#!/usr/bin/env python3
"""Build a +/- N day case window report anchored on a base case date.

Primary case date selection:
1) Docket entry containing "CASE INFORMATION ENTERED"
2) Case action event containing "INDICTED ORIGINAL"
3) Earliest docket filing date

Outputs a CSV listing each case in the date window, including the indictment (CR) PDF info.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATE_FMT = "%m/%d/%Y"
CASE_FILE_RE = re.compile(r"^(\d{4})-(\d{6})_(\d{8}_\d{6})\.json$")


@dataclass
class CaseRow:
    case_id: str
    case_number: int
    file_path: Path
    case_date: Optional[datetime]
    case_date_source: str
    case_info_entered_date: Optional[datetime]
    indicted_original_date: Optional[datetime]
    first_docket_date: Optional[datetime]
    indictment_date: Optional[datetime]
    indictment_desc: str
    indictment_pdf_filename: str
    indictment_pdf_path: str
    indictment_pdf_exists: bool


def parse_date(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, DATE_FMT)
    except ValueError:
        return None


def latest_case_files(year_dir: Path) -> Dict[str, Path]:
    latest: Dict[str, Tuple[str, Path]] = {}
    for p in year_dir.glob("*.json"):
        m = CASE_FILE_RE.match(p.name)
        if not m:
            continue
        year = int(m.group(1))
        number = int(m.group(2))
        ts = m.group(3)
        case_id = f"CR-{year % 100:02d}-{number:06d}-A"
        prev = latest.get(case_id)
        if prev is None or ts > prev[0]:
            latest[case_id] = (ts, p)
    return {k: v[1] for k, v in latest.items()}


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_case_dates(data: Dict[str, Any]) -> Tuple[Optional[datetime], Optional[datetime], Optional[datetime]]:
    docket = data.get("docket") or []
    case_info_entered_date: Optional[datetime] = None
    first_docket_date: Optional[datetime] = None

    for row in docket:
        if not isinstance(row, dict):
            continue
        d = parse_date(row.get("filing_date"))
        if d and (first_docket_date is None or d < first_docket_date):
            first_docket_date = d
        desc = (row.get("docket_description") or "").upper()
        if "CASE INFORMATION ENTERED" in desc and d is not None:
            if case_info_entered_date is None or d < case_info_entered_date:
                case_info_entered_date = d

    indicted_original_date: Optional[datetime] = None
    case_actions = ((data.get("summary") or {}).get("case_actions") or [])
    for action in case_actions:
        if not isinstance(action, dict):
            continue
        event = (action.get("event") or "").upper()
        if "INDICTED ORIGINAL" in event:
            d = parse_date(action.get("date"))
            if d is not None and (indicted_original_date is None or d < indicted_original_date):
                indicted_original_date = d

    return case_info_entered_date, indicted_original_date, first_docket_date


def pick_indictment_info(data: Dict[str, Any], case_id: str, repo_root: Path) -> Tuple[Optional[datetime], str, str, str, bool]:
    docket = data.get("docket") or []
    best: Optional[Dict[str, Any]] = None

    for row in docket:
        if not isinstance(row, dict):
            continue
        dtype = (row.get("docket_type") or row.get("document_type") or "").upper()
        if dtype != "CR":
            continue
        if best is None:
            best = row
        desc = (row.get("docket_description") or "").upper()
        if "INDICTED ORIGINAL" in desc:
            best = row
            break

    if not best:
        return None, "", "", "", False

    ind_date = parse_date(best.get("filing_date"))
    ind_desc = str(best.get("docket_description") or "")
    pdf_filename = str(best.get("pdf_filename") or "")
    pdf_path = repo_root / "out" / "2023" / "pdfs" / case_id / pdf_filename if pdf_filename else Path("")
    exists = bool(pdf_filename) and pdf_path.exists()
    return ind_date, ind_desc, pdf_filename, str(pdf_path), exists


def build_rows(repo_root: Path, year: int) -> List[CaseRow]:
    year_dir = repo_root / "out" / str(year)
    files = latest_case_files(year_dir)
    rows: List[CaseRow] = []

    for case_id, path in files.items():
        m = re.match(r"^CR-(\d{2})-(\d{6})-A$", case_id)
        if not m:
            continue
        case_number = int(m.group(2))
        data = load_json(path)
        case_info_date, indicted_original_date, first_docket_date = pick_case_dates(data)

        if case_info_date is not None:
            case_date = case_info_date
            source = "CASE INFORMATION ENTERED"
        elif indicted_original_date is not None:
            case_date = indicted_original_date
            source = "INDICTED ORIGINAL"
        else:
            case_date = first_docket_date
            source = "FIRST DOCKET DATE" if first_docket_date else "NONE"

        ind_date, ind_desc, ind_pdf_name, ind_pdf_path, ind_pdf_exists = pick_indictment_info(data, case_id, repo_root)

        rows.append(
            CaseRow(
                case_id=case_id,
                case_number=case_number,
                file_path=path,
                case_date=case_date,
                case_date_source=source,
                case_info_entered_date=case_info_date,
                indicted_original_date=indicted_original_date,
                first_docket_date=first_docket_date,
                indictment_date=ind_date,
                indictment_desc=ind_desc,
                indictment_pdf_filename=ind_pdf_name,
                indictment_pdf_path=ind_pdf_path,
                indictment_pdf_exists=ind_pdf_exists,
            )
        )

    return rows


def fmt_date(d: Optional[datetime]) -> str:
    return d.strftime(DATE_FMT) if d else ""


def classify_indictment(indictment_desc: str, indictment_pdf_exists: bool) -> str:
    if not indictment_pdf_exists:
        return "NO_INDICTMENT_PDF_FOUND"
    desc = (indictment_desc or "").upper()
    if "INDICTED ORIGINAL" in desc:
        return "ORIGINAL_INDICTMENT"
    if "BINDOVER" in desc:
        return "BINDOVER"
    return "OTHER_INDICTMENT_PDF"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build +/- day case window report using a canonical case date.")
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--base-case", default="CR-23-684826-A")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--output", default="out/2023/case_window_report_684826_pm30.csv")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    rows = build_rows(repo_root, args.year)
    rows_by_id = {r.case_id: r for r in rows}

    base = rows_by_id.get(args.base_case)
    if base is None:
        raise SystemExit(f"Base case {args.base_case} not found in latest {args.year} JSON files")
    if base.case_date is None:
        raise SystemExit(f"Base case {args.base_case} has no usable case date")

    lo = base.case_date - timedelta(days=args.window_days)
    hi = base.case_date + timedelta(days=args.window_days)

    in_window = [r for r in rows if r.case_date is not None and lo <= r.case_date <= hi]
    in_window.sort(key=lambda r: (r.case_date, r.case_number))

    out_path = repo_root / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "case_id",
            "case_number",
            "case_date",
            "case_date_source",
            "days_from_base",
            "base_case_id",
            "base_case_date",
            "case_info_entered_date",
            "indicted_original_date",
            "first_docket_date",
            "indictment_date",
            "indictment_type",
            "indictment_desc",
            "indictment_pdf_filename",
            "indictment_pdf_path",
            "indictment_pdf_exists",
            "json_file",
        ])

        for r in in_window:
            delta = (r.case_date - base.case_date).days if r.case_date else ""
            indictment_type = classify_indictment(r.indictment_desc, r.indictment_pdf_exists)
            w.writerow([
                r.case_id,
                r.case_number,
                fmt_date(r.case_date),
                r.case_date_source,
                delta,
                base.case_id,
                fmt_date(base.case_date),
                fmt_date(r.case_info_entered_date),
                fmt_date(r.indicted_original_date),
                fmt_date(r.first_docket_date),
                fmt_date(r.indictment_date),
                indictment_type,
                r.indictment_desc,
                r.indictment_pdf_filename,
                r.indictment_pdf_path,
                "yes" if r.indictment_pdf_exists else "no",
                str(r.file_path),
            ])

    print(f"Base case: {base.case_id}")
    print(f"Base case date ({base.case_date_source}): {fmt_date(base.case_date)}")
    print(f"Window: {fmt_date(lo)} to {fmt_date(hi)}")
    print(f"Cases in window: {len(in_window)}")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
