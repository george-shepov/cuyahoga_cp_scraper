#!/usr/bin/env python3
"""
Query + scheduled alert utilities for scraper operations.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "out"
LOGS_DIR = REPO_ROOT / "logs"
JOBS_FILE = LOGS_DIR / "query_jobs.json"
STATE_FILE = LOGS_DIR / "query_job_state.json"
ALERTS_FILE = LOGS_DIR / "query_alerts.log"
STATUTE_RE = re.compile(r"\b\d{4}\.\d+(?:\.[A-Z0-9]+)?")
CHARGE_HINT_TERMS = (
    "GUILTY TO",
    "AMENDED TO",
    "COUNT(S)",
    "COUNT ",
    "CHARGE",
    "OFFENSE",
    "NOLLED",
    "ACQUITT",
    "CONVICT",
)
PROCEDURAL_DOCKET_TERMS = (
    "SHERIFF SERVICE OF INDICTMENT",
    "SERVICE OF INDICTMENT",
    "MOTION TO TERMINATE CHARGES",
    "HEARING WAIVED",
    "INITIAL APPEARANCE SCHEDULED",
    "IS CANCELLED",
    "ARRAIGNMENT",
    "READING OF INDICTMENT WAIVED",
    "ORP - WARRANT ON INDICTMENT",
    "ORDERED TO TRANSPORT",
)
NON_CHARGE_DOCKET_TERMS = (
    "PAYMENT ON ACCOUNT",
    "REPARATION FEE",
    "COURT REPORTER FEE",
    "SHERIFF FEES",
    "COURT COST",
    "BOND REFUNDED",
    "BOOKING COST",
    "FEE BILL SUBMITTED",
    "SUPERVISION FEES",
    "DATE OF OFFENSE",
    "INDICTED ORIGINAL",
    "INDICTED BINDOVER",
    "ARRESTED",
    "PRETRIAL HELD",
    "CAPIAS",
)
PRIMARY_CRIME_TYPE_ORDER = {
    "VIOLENT": 0,
    "SEX": 1,
    "DRUG": 2,
    "PROPERTY": 3,
    "OTHER": 4,
}
NON_SUBSTANTIVE_STATUTE_PREFIXES = {"2743", "2949"}
SUMMARY_STATUTE_FIELD_KEYS = {
    "COMPLAINT",
    "INFORMATION",
    "CHARGE",
    "OFFENSE",
}


@dataclass
class QueryResult:
    rows: pd.DataFrame
    grouped: pd.DataFrame


def _split_terms(value: str) -> List[str]:
    return [x.strip() for x in str(value or "").split(";") if x.strip()]


def _normalize_charge_row(description: str, statute: str, disposition: str = "") -> Optional[Dict[str, str]]:
    normalized = {
        "charge_description": str(description or "").strip(),
        "statute": str(statute or "").strip(),
        "disposition": str(disposition or "").strip(),
    }
    if not any(normalized.values()):
        return None
    return normalized


def _is_non_charge_docket_entry(description: str) -> bool:
    text = str(description or "").strip().upper()
    if not text:
        return True
    return any(term in text for term in NON_CHARGE_DOCKET_TERMS)


def _parse_embedded_charge_rows(fields: Dict[str, Any]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not isinstance(fields, dict):
        return rows

    for value in fields.values():
        if not isinstance(value, dict):
            continue
        if str(value.get("format") or "").strip().lower() != "csv":
            continue
        csv_data = str(value.get("data") or "")
        if not csv_data.strip():
            continue

        try:
            reader = csv.DictReader(StringIO(csv_data))
        except csv.Error:
            continue

        fieldnames = {str(name or "").strip().lower() for name in (reader.fieldnames or [])}
        if "statute" not in fieldnames:
            continue
        if not ({"charge description", "charge_description", "description"} & fieldnames):
            continue

        for row in reader:
            if not isinstance(row, dict):
                continue
            normalized = _normalize_charge_row(
                row.get("Charge Description") or row.get("charge_description") or row.get("Description") or row.get("description") or "",
                row.get("Statute") or row.get("statute") or "",
                row.get("Disposition") or row.get("disposition") or "",
            )
            if normalized:
                rows.append(normalized)

    return rows


def _extract_summary_field_charge_rows(fields: Dict[str, Any]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not isinstance(fields, dict):
        return rows

    for key, value in fields.items():
        key_text = str(key or "").strip()
        value_text = str(value or "").strip()
        if not value_text:
            continue
        key_upper = key_text.rstrip(":").upper()
        if key_upper not in SUMMARY_STATUTE_FIELD_KEYS:
            continue
        statute_match = STATUTE_RE.search(value_text)
        normalized = _normalize_charge_row(key_upper, statute_match.group(0) if statute_match else value_text)
        if normalized:
            rows.append(normalized)

    return rows


def _extract_docket_charge_rows(docket: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for entry in docket:
        if not isinstance(entry, dict):
            continue
        description = str(entry.get("description", "") or "").strip()
        if not description or _is_non_charge_docket_entry(description):
            continue
        text = description.upper()
        if any(term in text for term in PROCEDURAL_DOCKET_TERMS):
            continue
        statute_match = STATUTE_RE.search(text)
        if not statute_match and not any(term in text for term in CHARGE_HINT_TERMS):
            continue
        normalized = _normalize_charge_row(description, statute_match.group(0) if statute_match else "")
        if normalized:
            rows.append(normalized)
    return rows


def _derive_charge_rows(
    summary_charges: List[Dict[str, Any]],
    fields: Dict[str, Any],
    docket: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    for charge in summary_charges:
        if not isinstance(charge, dict):
            continue
        normalized = _normalize_charge_row(
            charge.get("charge_description", ""),
            charge.get("statute", ""),
            charge.get("disposition", ""),
        )
        if normalized:
            rows.append(normalized)

    rows.extend(_parse_embedded_charge_rows(fields))
    rows.extend(_extract_summary_field_charge_rows(fields))
    rows.extend(_extract_docket_charge_rows(docket))

    deduped: List[Dict[str, str]] = []
    seen = set()
    for row in rows:
        key = (
            row["charge_description"].upper(),
            row["statute"].upper(),
            row["disposition"].upper(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


def _pick_primary_crime_type(crime_types: List[str]) -> str:
    filtered = [crime_type for crime_type in crime_types if crime_type and crime_type != "UNKNOWN"]
    if not filtered:
        return "OTHER"

    counts: Dict[str, int] = {}
    for crime_type in filtered:
        counts[crime_type] = counts.get(crime_type, 0) + 1

    ranked = sorted(
        counts.items(),
        key=lambda item: (-item[1], PRIMARY_CRIME_TYPE_ORDER.get(item[0], 99), item[0]),
    )
    return ranked[0][0]


def _classify_crime_type(description: str, statute: str) -> str:
    text = f"{description or ''} {statute or ''}".upper()
    if not text.strip():
        return "UNKNOWN"

    # Ignore known non-charge/cost statutes that can appear in noisy docket-derived text.
    statute_text = str(statute or "")
    m = re.search(r"\b(\d{4})", statute_text)
    if m and m.group(1) in NON_SUBSTANTIVE_STATUTE_PREFIXES:
        return "UNKNOWN"
    if any(term in text for term in ["DEFENDANT DECLARED INDIGENT", "COURT COST", "FEE BILL SUBMITTED"]):
        return "UNKNOWN"

    violent_terms = [
        "MURDER",
        "HOMICIDE",
        "ASSAULT",
        "ROBBERY",
        "KIDNAP",
        "DOMESTIC VIOLENCE",
        "MENACING",
        "AGGRAVATED",
        "FELONIOUS",
        "WEAPON",
        "FIREARM",
        "FAILURE TO COMPLY WITH ORDER,SIGNAL OF POLICE OFFICER",
        "OBSTRUCTING OFFICIAL BUSINESS",
        "OBSTRUCTING JUSTICE",
        "RESISTING ARREST",
        "TAMPERING WITH EVIDENCE",
        "HAVING WEAPONS WHILE UNDER DISABILITY",
        "IMPROPERLY HANDLING FIREARMS",
        "FUGITIVE",
        "CRUELTY AGAINST COMPANION ANIMAL",
        "MENACING BY STALKING",
    ]
    drug_terms = [
        "DRUG",
        "COCAINE",
        "HEROIN",
        "FENTANYL",
        "MARIJUANA",
        "TRAFFICKING",
        "POSSESSION",
        "CONTROLLED SUBSTANCE",
        "NARCOT",
    ]
    property_terms = [
        "THEFT",
        "BURGLARY",
        "ROBBERY",
        "TRESPASS",
        "FORGERY",
        "FRAUD",
        "RECEIVING STOLEN",
        "VANDAL",
        "ARSON",
        "CRIMINAL DAMAGING",
        "IDENTITY FRAUD",
        "BREAKING AND ENTERING",
        "STOPPING AFTER ACCIDENT",
    ]
    sex_terms = [
        "RAPE",
        "SEXUAL",
        "GROSS SEXUAL",
        "PORNOGRAPH",
        "UNLAWFUL SEX",
        "IMPORTUN",
    ]

    if any(t in text for t in sex_terms):
        return "SEX"
    if any(t in text for t in violent_terms):
        return "VIOLENT"
    if any(t in text for t in drug_terms):
        return "DRUG"
    if any(t in text for t in property_terms):
        return "PROPERTY"

    # Fallback to statute-family mapping for Ohio code sections when description text is sparse.
    m = re.search(r"\b(\d{4})", statute_text)
    if m:
        code = int(m.group(1))
        if code in {2903, 2905, 2909, 2919, 2923}:
            return "VIOLENT"
        if code == 2907:
            return "SEX"
        if code == 2925:
            return "DRUG"
        if code in {2911, 2913}:
            return "PROPERTY"
        if code in {2921, 2963}:
            return "VIOLENT"
        if code == 2950:
            return "SEX"
        if code in {4510, 4511, 4549}:
            return "PROPERTY"
        if code in {1315, 3772}:
            return "PROPERTY"
        if code == 2927:
            return "VIOLENT"

    return "OTHER"


def _parse_mmddyyyy(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        return datetime.strptime(text, "%m/%d/%Y")
    except Exception:
        return None


def _parse_case_date(value: str) -> Optional[datetime]:
    """Parse either MM/DD/YYYY or YYYY-MM-DD date strings."""
    text = str(value or "").strip()
    if not text or text.upper() == "N/A":
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _compute_outcome_and_resolution(
    fields: Dict[str, Any],
    charges: List[Dict[str, Any]],
    case_actions: List[Dict[str, Any]],
) -> Tuple[str, Optional[int], Optional[str], Optional[str]]:
    """
    Infer case outcome bucket and time-to-resolution in days.

    Returns: (outcome_bucket, resolution_days, start_date_iso, resolution_date_iso)
    """
    favorable_terms = [
        "DISMISS",
        "DISMISSED",
        "NOLLE",
        "NO BILL",
        "ACQUITT",
        "NOT GUILTY",
        "WITHDRAWN",
    ]
    unfavorable_terms = [
        "PLD GLTY",
        "GLTY",
        "GUILTY",
        "CONVICT",
        "CONV",
        "SENTENCE",
        "PRISON",
        "JAIL",
        "COMMUNITY CONTROL",
    ]

    disposition_texts: List[str] = []
    for ch in charges:
        if not isinstance(ch, dict):
            continue
        disp = str(ch.get("disposition", "") or "").strip().upper()
        if disp:
            disposition_texts.append(disp)

    has_favorable = any(any(term in disp for term in favorable_terms) for disp in disposition_texts)
    has_unfavorable = any(any(term in disp for term in unfavorable_terms) for disp in disposition_texts)

    if has_favorable and has_unfavorable:
        outcome_bucket = "MIXED"
    elif has_favorable:
        outcome_bucket = "FAVORABLE"
    elif has_unfavorable:
        outcome_bucket = "UNFAVORABLE"
    else:
        outcome_bucket = "UNKNOWN"

    start_dt = _parse_mmddyyyy(str(fields.get("Arrested Date:", "") or ""))

    action_dates: List[datetime] = []
    for action in case_actions:
        if not isinstance(action, dict):
            continue
        action_dt = _parse_mmddyyyy(str(action.get("date", "") or ""))
        if action_dt:
            action_dates.append(action_dt)

    resolution_dt = max(action_dates) if action_dates else None
    if not start_dt and action_dates:
        start_dt = min(action_dates)
    resolution_days = None
    if start_dt and resolution_dt and resolution_dt >= start_dt:
        resolution_days = (resolution_dt - start_dt).days

    return (
        outcome_bucket,
        resolution_days,
        start_dt.date().isoformat() if start_dt else None,
        resolution_dt.date().isoformat() if resolution_dt else None,
    )


def _compute_disposition_signals(charges: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract case-level disposition signals from charge dispositions."""
    texts: List[str] = []
    for ch in charges:
        if not isinstance(ch, dict):
            continue
        disp = str(ch.get("disposition", "") or "").strip().upper()
        if disp:
            texts.append(disp)

    has_dismissal = any(
        any(term in t for term in ["DISMISS", "NOLLE", "NO BILL", "WITHDRAWN"])
        for t in texts
    )
    has_conviction_related = any(
        any(term in t for term in ["GUILTY", "GLTY", "CONVICT", "SENTENCE", "JAIL", "PRISON", "COMMUNITY CONTROL"])
        for t in texts
    )
    plea_indicated = any(
        any(term in t for term in ["PLD", "PLEA", "NO CONTEST", "N/C"])
        for t in texts
    )
    trial_indicated = any(
        any(term in t for term in ["TRIAL", "VERDICT", "ACQUITT", "NOT GUILTY"])
        for t in texts
    )

    if plea_indicated and not trial_indicated:
        disposition_mode = "PLEA"
    elif trial_indicated and not plea_indicated:
        disposition_mode = "TRIAL"
    elif plea_indicated and trial_indicated:
        disposition_mode = "MIXED"
    else:
        disposition_mode = "UNKNOWN"

    return {
        "dismissal_flag": has_dismissal,
        "conviction_related_flag": has_conviction_related,
        "plea_flag": plea_indicated,
        "trial_flag": trial_indicated,
        "disposition_mode": disposition_mode,
    }


def _representation_bucket(defense_entries: List[Dict[str, Any]]) -> str:
    if not defense_entries:
        return "UNKNOWN"

    for entry in defense_entries:
        role = str(entry.get("role", "") or "").upper()
        atype = str(entry.get("type", "") or "").upper()
        if "PUBLIC DEFENDER" in role or "PUBLIC DEFENDER" in atype:
            return "INDIGENT"

    for entry in defense_entries:
        atype = str(entry.get("type", "") or "").upper()
        role = str(entry.get("role", "") or "").upper()
        if "RETAINED" in atype or "ATTORNEY OF RECORD" in role:
            return "PAYING"

    return "UNKNOWN"


def _normalize_terms(text_value: str, selected_values: Optional[List[str]]) -> List[str]:
    terms: List[str] = []

    tv = str(text_value or "").strip()
    if tv:
        terms.append(tv)

    if isinstance(selected_values, list):
        for v in selected_values:
            s = str(v or "").strip()
            if s:
                terms.append(s)

    seen = set()
    out: List[str] = []
    for t in terms:
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _contains_any(series: pd.Series, terms: List[str]) -> pd.Series:
    pattern = "|".join(re.escape(t) for t in terms)
    return series.astype(str).str.contains(pattern, case=False, na=False, regex=True)


def _parse_filename_ts(path: Path) -> datetime:
    m = re.search(r"_(\d{8}_\d{6})\.json$", path.name)
    if not m:
        return datetime.min
    try:
        return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
    except Exception:
        return datetime.min


def _load_latest_files() -> Dict[Tuple[int, int], Path]:
    latest: Dict[Tuple[int, int], Path] = {}
    for year_dir in OUT_DIR.glob("20*"):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        year = int(year_dir.name)
        for p in year_dir.glob("*.json"):
            m = re.match(r"^(\d{4})-(\d{6})_", p.name)
            if not m:
                continue
            num = int(m.group(2))
            key = (year, num)
            prev = latest.get(key)
            if prev is None or _parse_filename_ts(p) >= _parse_filename_ts(prev):
                latest[key] = p
    return latest


def _safe_list(obj: Any) -> List[Any]:
    return obj if isinstance(obj, list) else []


def build_latest_dataset() -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    latest = _load_latest_files()
    for (year, number), p in latest.items():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        meta = data.get("metadata", {}) if isinstance(data, dict) else {}
        summary = data.get("summary", {}) if isinstance(data, dict) else {}
        fields = summary.get("fields", {}) if isinstance(summary, dict) else {}
        attorneys = _safe_list(data.get("attorneys"))
        docket = _safe_list(data.get("docket"))
        costs = data.get("costs", [])
        summary_charges = _safe_list(summary.get("charges"))
        case_actions = _safe_list(summary.get("case_actions"))
        charge_rows = _derive_charge_rows(summary_charges, fields if isinstance(fields, dict) else {}, docket)

        pros: List[str] = []
        defs: List[str] = []
        attorney_names: List[str] = []
        defense_entries: List[Dict[str, Any]] = []
        for a in attorneys:
            if not isinstance(a, dict):
                continue
            name = str(a.get("name", "") or "").strip()
            if not name:
                continue
            attorney_names.append(name)
            party = str(a.get("party", "") or "").upper()
            role = str(a.get("role", "") or "").upper()
            atype = str(a.get("type", "") or "").upper()
            is_pros = (
                "PROSECUTION" in party
                or "PROSECUTOR" in role
                or "PROSECUTING ATTORNEY" in role
                or "STATE ATTORNEY" in atype
                or party == "STATE"
            )
            if is_pros:
                pros.append(name)
            else:
                defs.append(name)
                defense_entries.append(a)

        crime_types = [
            _classify_crime_type(ch.get("charge_description", ""), ch.get("statute", ""))
            for ch in charge_rows
        ]
        unique_crime_types = sorted({ct for ct in crime_types if ct and ct != "UNKNOWN"})
        if not unique_crime_types:
            unique_crime_types = ["OTHER"]
        primary_crime_type = _pick_primary_crime_type(crime_types)

        outcome_bucket, resolution_days, start_date, resolution_date = _compute_outcome_and_resolution(
            fields if isinstance(fields, dict) else {},
            charge_rows,
            [a for a in case_actions if isinstance(a, dict)],
        )
        disposition_signals = _compute_disposition_signals(charge_rows)

        event_dates: List[datetime] = []
        for entry in docket:
            if not isinstance(entry, dict):
                continue
            for key in ("date", "proceeding_date", "filing_date"):
                dt = _parse_case_date(str(entry.get(key, "") or ""))
                if dt:
                    event_dates.append(dt)

        for action in case_actions:
            if not isinstance(action, dict):
                continue
            dt = _parse_case_date(str(action.get("date", "") or ""))
            if dt:
                event_dates.append(dt)

        created_dt = min(event_dates) if event_dates else None
        updated_dt = max(event_dates) if event_dates else None

        file_scrape_dt = _parse_filename_ts(p)
        downloaded_last_at = None
        if file_scrape_dt != datetime.min:
            downloaded_last_at = file_scrape_dt.isoformat(timespec="seconds")

        representation_bucket = _representation_bucket(defense_entries)
        retained_count = 0
        public_defender_count = 0
        for entry in defense_entries:
            role = str(entry.get("role", "") or "").upper()
            atype = str(entry.get("type", "") or "").upper()
            if "RETAINED" in atype:
                retained_count += 1
            if "PUBLIC DEFENDER" in role or "PUBLIC DEFENDER" in atype:
                public_defender_count += 1

        case_id = meta.get("case_id")
        if not case_id:
            case_id = f"{year}-{number:06d}"

        status = fields.get("Status:") if isinstance(fields, dict) else None
        judge = fields.get("Judge Name:") if isinstance(fields, dict) else None
        defendant = fields.get("Name:") if isinstance(fields, dict) else None

        rows.append(
            {
                "case_id": str(case_id or ""),
                "year": year,
                "number": number,
                "judge": str(judge or ""),
                "status": str(status or ""),
                "defendant": str(defendant or ""),
                "exists": bool(meta.get("exists", False)),
                "docket_count": len(docket),
                "attorney_count": len(attorneys),
                "cost_item_count": len(costs) if isinstance(costs, list) else 0,
                "prosecutors": "; ".join(sorted(set(pros))),
                "attorneys": "; ".join(sorted(set(defs))),
                "all_attorneys": "; ".join(sorted(set(attorney_names))),
                "representation_bucket": representation_bucket,
                "retained_count": retained_count,
                "public_defender_count": public_defender_count,
                "crime_types": "; ".join(unique_crime_types),
                "primary_crime_type": primary_crime_type,
                "charge_count": len(charge_rows),
                "outcome_bucket": outcome_bucket,
                "favorable_outcome": outcome_bucket == "FAVORABLE",
                "resolution_days": resolution_days,
                "case_start_date": start_date or "",
                "case_resolution_date": resolution_date or "",
                "case_created_date": created_dt.date().isoformat() if created_dt else "",
                "last_case_update_date": updated_dt.date().isoformat() if updated_dt else "",
                "downloaded_last_at": downloaded_last_at or str(meta.get("scraped_at") or ""),
                "dismissal_flag": disposition_signals["dismissal_flag"],
                "conviction_related_flag": disposition_signals["conviction_related_flag"],
                "plea_flag": disposition_signals["plea_flag"],
                "trial_flag": disposition_signals["trial_flag"],
                "disposition_mode": disposition_signals["disposition_mode"],
                "file": str(p.relative_to(REPO_ROOT)),
                "scraped_at": str(meta.get("scraped_at") or ""),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "case_id",
                "year",
                "number",
                "judge",
                "status",
                "defendant",
                "exists",
                "docket_count",
                "attorney_count",
                "cost_item_count",
                "prosecutors",
                "attorneys",
                "all_attorneys",
                "representation_bucket",
                "retained_count",
                "public_defender_count",
                "crime_types",
                "primary_crime_type",
                "charge_count",
                "outcome_bucket",
                "favorable_outcome",
                "resolution_days",
                "case_start_date",
                "case_resolution_date",
                "case_created_date",
                "last_case_update_date",
                "downloaded_last_at",
                "dismissal_flag",
                "conviction_related_flag",
                "plea_flag",
                "trial_flag",
                "disposition_mode",
                "file",
                "scraped_at",
            ]
        )

    return pd.DataFrame(rows).sort_values(["year", "number"]).reset_index(drop=True)


def run_query(
    df: pd.DataFrame,
    years: Optional[List[int]] = None,
    judge_contains: str = "",
    judge_selected: Optional[List[str]] = None,
    status_contains: str = "",
    status_selected: Optional[List[str]] = None,
    defendant_contains: str = "",
    prosecutor_contains: str = "",
    prosecutor_selected: Optional[List[str]] = None,
    attorney_contains: str = "",
    attorney_selected: Optional[List[str]] = None,
    only_existing: bool = False,
    group_by: Optional[List[str]] = None,
) -> QueryResult:
    work = df.copy()

    if years:
        work = work[work["year"].isin(years)]

    judge_terms = _normalize_terms(judge_contains, judge_selected)
    if judge_terms:
        work = work[_contains_any(work["judge"], judge_terms)]

    status_terms = _normalize_terms(status_contains, status_selected)
    if status_terms:
        work = work[_contains_any(work["status"], status_terms)]

    if defendant_contains:
        work = work[work["defendant"].str.contains(defendant_contains, case=False, na=False)]

    prosecutor_terms = _normalize_terms(prosecutor_contains, prosecutor_selected)
    if prosecutor_terms:
        work = work[_contains_any(work["prosecutors"], prosecutor_terms)]

    attorney_terms = _normalize_terms(attorney_contains, attorney_selected)
    if attorney_terms:
        work = work[_contains_any(work["all_attorneys"], attorney_terms)]

    if only_existing:
        work = work[work["exists"] == True]

    group_by = group_by or []
    if group_by:
        grouped = (
            work.groupby(group_by, dropna=False)
            .agg(
                case_count=("case_id", "count"),
                avg_docket_count=("docket_count", "mean"),
            )
            .reset_index()
            .sort_values("case_count", ascending=False)
        )
        grouped["avg_docket_count"] = grouped["avg_docket_count"].round(2)
    else:
        grouped = pd.DataFrame()

    return QueryResult(rows=work.reset_index(drop=True), grouped=grouped)


def load_jobs() -> List[Dict[str, Any]]:
    if not JOBS_FILE.exists():
        return []
    try:
        data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if isinstance(item, dict):
            out.append(item)
    return out


def save_jobs(jobs: List[Dict[str, Any]]) -> None:
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def load_job_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {"last_runs": {}}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"last_runs": {}}
        data.setdefault("last_runs", {})
        return data
    except Exception:
        return {"last_runs": {}}


def save_job_state(state: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _now() -> datetime:
    return datetime.now()


def due_to_run(job: Dict[str, Any], state: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    now = now or _now()
    if not bool(job.get("enabled", True)):
        return False

    interval_minutes = int(job.get("interval_minutes", 60))
    jid = str(job.get("id", ""))
    if not jid:
        return False

    last_runs = state.get("last_runs", {})
    if not isinstance(last_runs, dict):
        return True

    ts = last_runs.get(jid)
    if not ts:
        return True

    try:
        last_dt = datetime.fromisoformat(str(ts))
    except Exception:
        return True

    return now >= (last_dt + timedelta(minutes=max(1, interval_minutes)))


def _condition_met(result_rows: int, condition: Dict[str, Any]) -> bool:
    op = str(condition.get("op", ">="))
    value = int(condition.get("value", 1))

    if op == ">=":
        return result_rows >= value
    if op == ">":
        return result_rows > value
    if op == "==":
        return result_rows == value
    if op == "<=":
        return result_rows <= value
    if op == "<":
        return result_rows < value
    return result_rows >= value


def append_query_alert(message: str) -> None:
    ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = _now().isoformat(timespec="seconds")
    with ALERTS_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def run_job_once(df: pd.DataFrame, job: Dict[str, Any]) -> Dict[str, Any]:
    q = job.get("query", {}) if isinstance(job.get("query"), dict) else {}
    group_by = q.get("group_by", [])
    if not isinstance(group_by, list):
        group_by = []

    result = run_query(
        df,
        years=q.get("years") if isinstance(q.get("years"), list) else None,
        judge_contains=str(q.get("judge_contains", "") or ""),
        judge_selected=q.get("judge_selected") if isinstance(q.get("judge_selected"), list) else None,
        status_contains=str(q.get("status_contains", "") or ""),
        status_selected=q.get("status_selected") if isinstance(q.get("status_selected"), list) else None,
        defendant_contains=str(q.get("defendant_contains", "") or ""),
        prosecutor_contains=str(q.get("prosecutor_contains", "") or ""),
        prosecutor_selected=q.get("prosecutor_selected") if isinstance(q.get("prosecutor_selected"), list) else None,
        attorney_contains=str(q.get("attorney_contains", "") or ""),
        attorney_selected=q.get("attorney_selected") if isinstance(q.get("attorney_selected"), list) else None,
        only_existing=bool(q.get("only_existing", False)),
        group_by=group_by,
    )

    row_count = int(len(result.rows))

    cond = job.get("alert_condition", {"op": ">=", "value": 1})
    if not isinstance(cond, dict):
        cond = {"op": ">=", "value": 1}

    triggered = _condition_met(row_count, cond)
    if triggered:
        append_query_alert(
            f"JOB_TRIGGERED id={job.get('id')} name={job.get('name')} rows={row_count} condition={cond}"
        )

    return {
        "job_id": str(job.get("id", "")),
        "job_name": str(job.get("name", "")),
        "rows": row_count,
        "triggered": triggered,
        "ran_at": _now().isoformat(timespec="seconds"),
    }
