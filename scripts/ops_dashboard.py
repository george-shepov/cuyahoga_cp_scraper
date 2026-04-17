#!/usr/bin/env python3
"""
Interactive operations dashboard for scraper health and data freshness.

Run:
  streamlit run scripts/ops_dashboard.py
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from query_jobs import (
    build_latest_dataset,
    load_jobs,
    load_job_state,
    run_job_once,
    run_query,
    save_jobs,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "out"
LOGS_DIR = REPO_ROOT / "logs"
STATE_FILE = LOGS_DIR / "daily_streams_state.json"
ALERTS_FILE = LOGS_DIR / "case_change_alerts.log"
QUERY_ALERTS_FILE = LOGS_DIR / "query_alerts.log"


def parse_ts_from_filename(path: Path) -> Optional[datetime]:
    m = re.search(r"_(\d{8}_\d{6})\.json$", path.name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def case_number_from_file(path: Path) -> Optional[Tuple[int, int]]:
    m = re.match(r"^(\d{4})-(\d{6})_", path.name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


@st.cache_data(ttl=60)
def list_years() -> List[int]:
    years: List[int] = []
    for p in OUT_DIR.glob("20*"):
        if p.is_dir() and p.name.isdigit():
            years.append(int(p.name))
    return sorted(years)


@st.cache_data(ttl=60)
def load_state() -> Dict:
    if not STATE_FILE.exists():
        return {
            "consecutive_errors": 0,
            "cooldown_until": None,
            "last_run": None,
            "retry_queue": {},
        }
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("retry_queue", {})
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {
        "consecutive_errors": 0,
        "cooldown_until": None,
        "last_run": None,
        "retry_queue": {},
    }


@st.cache_data(ttl=60)
def collect_file_inventory() -> pd.DataFrame:
    rows = []
    for year in list_years():
        year_dir = OUT_DIR / str(year)
        for p in year_dir.glob("*.json"):
            parsed = case_number_from_file(p)
            if not parsed:
                continue
            ts = parse_ts_from_filename(p)
            rows.append(
                {
                    "year": parsed[0],
                    "number": parsed[1],
                    "file": str(p.relative_to(REPO_ROOT)),
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime),
                    "scrape_ts": ts,
                    "size_kb": round(p.stat().st_size / 1024.0, 2),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["year", "number", "file", "mtime", "scrape_ts", "size_kb"])
    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def latest_per_case(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work["rank_ts"] = work["scrape_ts"].fillna(work["mtime"])
    work = work.sort_values(["year", "number", "rank_ts"]).drop_duplicates(["year", "number"], keep="last")
    return work.drop(columns=["rank_ts"])  # type: ignore[return-value]


@st.cache_data(ttl=60)
def gap_stats(latest_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if latest_df.empty:
        return pd.DataFrame(columns=["year", "min", "max", "present", "missing", "gap_density"])

    for year, ydf in latest_df.groupby("year"):
        nums = sorted(ydf["number"].astype(int).tolist())
        if not nums:
            continue
        mn, mx = nums[0], nums[-1]
        expected = max(0, mx - mn + 1)
        present = len(set(nums))
        missing = max(0, expected - present)
        density = (missing / expected) if expected else 0.0
        rows.append(
            {
                "year": int(year),
                "min": mn,
                "max": mx,
                "present": present,
                "missing": missing,
                "gap_density": round(density, 4),
            }
        )
    return pd.DataFrame(rows).sort_values("year")


@st.cache_data(ttl=60)
def failed_latest_cases(latest_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in latest_df.iterrows():
        p = REPO_ROOT / str(r["file"])
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            rows.append(
                {
                    "year": int(r["year"]),
                    "number": int(r["number"]),
                    "file": str(r["file"]),
                    "exists": None,
                    "error": "invalid json",
                }
            )
            continue

        meta = obj.get("metadata", {}) if isinstance(obj, dict) else {}
        exists = meta.get("exists", None)
        errs = obj.get("errors", []) if isinstance(obj, dict) else []
        err_text = ""
        if isinstance(errs, list) and errs:
            first = errs[0]
            if isinstance(first, dict):
                err_text = str(first.get("message", ""))
            else:
                err_text = str(first)

        if exists is False or err_text:
            rows.append(
                {
                    "year": int(r["year"]),
                    "number": int(r["number"]),
                    "file": str(r["file"]),
                    "exists": exists,
                    "error": err_text,
                }
            )

    if not rows:
        return pd.DataFrame(columns=["year", "number", "file", "exists", "error"])
    return pd.DataFrame(rows).sort_values(["year", "number"])


def normalized_payload_hash_from_obj(obj: Dict) -> str:
    obj = dict(obj)
    meta = obj.get("metadata")
    if isinstance(meta, dict):
        meta.pop("scraped_at", None)
    errs = obj.get("errors")
    if isinstance(errs, list):
        for e in errs:
            if isinstance(e, dict):
                e.pop("timestamp", None)
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@st.cache_data(ttl=60)
def case_history(year: int, number: int) -> pd.DataFrame:
    year_dir = OUT_DIR / str(year)
    rows = []
    if not year_dir.exists():
        return pd.DataFrame(columns=["file", "scrape_ts", "exists", "hash", "size_kb"])

    pattern = f"{year}-{number:06d}_*.json"
    files = sorted(year_dir.glob(pattern), key=lambda p: parse_ts_from_filename(p) or datetime.min)

    for p in files:
        exists_val = None
        hash_val = ""
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            exists_val = (obj.get("metadata", {}) or {}).get("exists")
            hash_val = normalized_payload_hash_from_obj(obj)
        except (json.JSONDecodeError, OSError):
            hash_val = "<invalid-json>"

        rows.append(
            {
                "file": str(p.relative_to(REPO_ROOT)),
                "scrape_ts": parse_ts_from_filename(p),
                "exists": exists_val,
                "hash": hash_val,
                "size_kb": round(p.stat().st_size / 1024.0, 2),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["file", "scrape_ts", "exists", "hash", "size_kb"])

    out = pd.DataFrame(rows)
    out["changed_vs_prev"] = out["hash"].ne(out["hash"].shift(1))
    out.loc[out.index[0], "changed_vs_prev"] = True
    return out


@st.cache_data(ttl=60)
def load_alerts(limit: int = 400) -> pd.DataFrame:
    if not ALERTS_FILE.exists():
        return pd.DataFrame(columns=["ts", "message"])
    lines = ALERTS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
    rows = []
    for line in lines:
        m = re.match(r"^\[(.*?)\]\s+(.*)$", line)
        if m:
            rows.append({"ts": m.group(1), "message": m.group(2)})
        else:
            rows.append({"ts": "", "message": line})
    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def load_query_alerts(limit: int = 400) -> pd.DataFrame:
    if not QUERY_ALERTS_FILE.exists():
        return pd.DataFrame(columns=["ts", "message"])
    lines = QUERY_ALERTS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
    rows = []
    for line in lines:
        m = re.match(r"^\[(.*?)\]\s+(.*)$", line)
        if m:
            rows.append({"ts": m.group(1), "message": m.group(2)})
        else:
            rows.append({"ts": "", "message": line})
    return pd.DataFrame(rows)


def _non_empty_unique(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for v in values:
        s = str(v or "").strip()
        if not s:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def _split_semicolon_values(series: pd.Series) -> List[str]:
    vals: List[str] = []
    for raw in series.fillna("").astype(str).tolist():
        parts = [p.strip() for p in raw.split(";")]
        vals.extend([p for p in parts if p])
    return _non_empty_unique(vals)


def _split_semicolon_scalar(value: str) -> List[str]:
    return [p.strip() for p in str(value or "").split(";") if p.strip()]


def _exploded_links(df: pd.DataFrame, left_col: str, right_col: str) -> pd.DataFrame:
    rows: List[Dict[str, str]] = []
    for _, r in df.iterrows():
        left_values = _split_semicolon_scalar(str(r.get(left_col, "") or ""))
        right_values = _split_semicolon_scalar(str(r.get(right_col, "") or ""))
        if not left_values or not right_values:
            continue
        for lv in left_values:
            for rv in right_values:
                rows.append({left_col: lv, right_col: rv})
    if not rows:
        return pd.DataFrame(columns=[left_col, right_col, "case_count"])
    out = pd.DataFrame(rows).groupby([left_col, right_col], dropna=False).size().reset_index(name="case_count")
    return out.sort_values("case_count", ascending=False)


def _top_k(df: pd.DataFrame, k: int = 25) -> pd.DataFrame:
    if df.empty:
        return df
    return df.head(max(1, k)).reset_index(drop=True)


def _is_pending_status(value: str) -> bool:
    text = str(value or "").upper()
    if not text:
        return True
    pending_tokens = [
        "PEND",
        "ACTIVE",
        "OPEN",
        "TRIAL",
        "ARRAIGN",
        "PRETRIAL",
        "BOND",
        "JAIL",
        "WARRANT",
        "DEFN",
    ]
    return any(token in text for token in pending_tokens)


@st.cache_data(ttl=120)
def build_overall_stat_frames() -> Dict[str, pd.DataFrame]:
    df = build_latest_dataset()
    if df.empty:
        empty = pd.DataFrame()
        return {
            "base": empty,
            "new_cases": empty,
            "crime_counts": empty,
            "crime_by_year": empty,
            "crime_mom": empty,
            "judge_concentration": empty,
            "prosecutor_concentration": empty,
            "judge_metrics": empty,
            "prosecutor_metrics": empty,
            "backlog_buckets": empty,
            "field_completeness": empty,
            "judge_load": empty,
            "pros_load": empty,
            "attorney_load": empty,
            "judge_crime": empty,
            "pros_crime": empty,
            "attorney_crime": empty,
            "pros_judge": empty,
        }

    work = df.copy()
    work["scraped_dt"] = pd.to_datetime(work["scraped_at"], errors="coerce", utc=True).dt.tz_convert(None)
    work["scraped_month"] = work["scraped_dt"].dt.to_period("M").astype(str)
    work["case_start_dt"] = pd.to_datetime(work["case_start_date"], errors="coerce")
    work["case_resolution_dt"] = pd.to_datetime(work["case_resolution_date"], errors="coerce")

    today = pd.Timestamp(datetime.utcnow().date())
    start_fallback = work["case_start_dt"].fillna(work["scraped_dt"])
    work["pending_age_days"] = (today - start_fallback).dt.days

    new_cases = (
        work.groupby(["year", "scraped_month"], dropna=False)
        .size()
        .reset_index(name="case_count")
        .sort_values(["year", "scraped_month"])
    )

    crime_counts = (
        work.groupby("primary_crime_type", dropna=False)
        .size()
        .reset_index(name="case_count")
        .sort_values("case_count", ascending=False)
    )

    crime_by_year = (
        work.groupby(["year", "primary_crime_type"], dropna=False)
        .size()
        .reset_index(name="case_count")
        .sort_values(["year", "case_count"], ascending=[True, False])
    )

    crime_mom = (
        work.groupby(["scraped_month", "primary_crime_type"], dropna=False)
        .size()
        .reset_index(name="case_count")
        .sort_values(["primary_crime_type", "scraped_month"])
    )
    if not crime_mom.empty:
        crime_mom["prev_month_count"] = crime_mom.groupby("primary_crime_type", dropna=False)["case_count"].shift(1)
        crime_mom["mom_delta"] = crime_mom["case_count"] - crime_mom["prev_month_count"].fillna(0)
        crime_mom["mom_pct"] = (
            (crime_mom["mom_delta"] / crime_mom["prev_month_count"].replace(0, pd.NA)) * 100
        ).round(1)
        crime_mom["mom_pct"] = crime_mom["mom_pct"].fillna(0.0)
        crime_mom["mom_delta"] = crime_mom["mom_delta"].astype(int)

    judge_crime_counts = (
        work.groupby(["primary_crime_type", "judge"], dropna=False)
        .size()
        .reset_index(name="case_count")
    )
    judge_concentration = pd.DataFrame(
        columns=[
            "crime",
            "total_cases",
            "unique_judges",
            "top_judge",
            "top_judge_cases",
            "top_judge_share_pct",
            "hhi",
            "effective_judges",
        ]
    )
    if not judge_crime_counts.empty:
        judge_concentration = (
            judge_crime_counts.groupby("primary_crime_type", dropna=False)
            .apply(
                lambda g: pd.Series(
                    {
                        "total_cases": int(g["case_count"].sum()),
                        "unique_judges": int(g["judge"].replace("", pd.NA).dropna().nunique()),
                        "top_judge": str(g.sort_values("case_count", ascending=False).iloc[0]["judge"] or ""),
                        "top_judge_cases": int(g["case_count"].max()),
                        "top_judge_share_pct": round(float(g["case_count"].max() / max(1, g["case_count"].sum()) * 100), 1),
                        "hhi": round(float(((g["case_count"] / max(1, g["case_count"].sum())) ** 2).sum()), 4),
                    }
                )
            )
            .reset_index()
            .rename(columns={"primary_crime_type": "crime"})
            .sort_values("hhi", ascending=False)
        )
        judge_concentration["effective_judges"] = judge_concentration["hhi"].apply(
            lambda x: round((1.0 / x), 2) if x and x > 0 else 0.0
        )


    judge_load = (
        work.groupby("judge", dropna=False)
        .agg(
            case_count=("case_id", "count"),
            unique_prosecutors=("prosecutors", "nunique"),
            unique_attorneys=("attorneys", "nunique"),
            avg_charge_count=("charge_count", "mean"),
        )
        .reset_index()
        .sort_values("case_count", ascending=False)
    )
    judge_load["avg_charge_count"] = judge_load["avg_charge_count"].round(2)

    judge_metrics = (
        work.groupby("judge", dropna=False)
        .agg(
            case_count=("case_id", "count"),
            median_charges_per_case=("charge_count", "median"),
            median_disposition_days=("resolution_days", "median"),
            plea_cases=("plea_flag", "sum"),
            trial_cases=("trial_flag", "sum"),
        )
        .reset_index()
    )
    judge_metrics["median_charges_per_case"] = judge_metrics["median_charges_per_case"].round(2)
    judge_metrics["median_disposition_days"] = judge_metrics["median_disposition_days"].fillna(0).round(1)
    split_den = (judge_metrics["plea_cases"] + judge_metrics["trial_cases"]).replace(0, pd.NA)
    judge_metrics["plea_share_pct"] = ((judge_metrics["plea_cases"] / split_den) * 100).fillna(0).round(1)
    judge_metrics["trial_share_pct"] = ((judge_metrics["trial_cases"] / split_den) * 100).fillna(0).round(1)
    judge_metrics = judge_metrics.sort_values("case_count", ascending=False)

    pros_rows: List[Dict[str, object]] = []
    attorney_rows: List[Dict[str, object]] = []
    for _, r in work.iterrows():
        pros = _split_semicolon_scalar(str(r.get("prosecutors", "") or ""))
        atts = _split_semicolon_scalar(str(r.get("attorneys", "") or ""))
        crime = str(r.get("primary_crime_type", "UNKNOWN") or "UNKNOWN")
        judge = str(r.get("judge", "") or "")
        rep = str(r.get("representation_bucket", "UNKNOWN") or "UNKNOWN")
        outcome = str(r.get("outcome_bucket", "UNKNOWN") or "UNKNOWN")
        favorable_score = 1.0 if outcome == "FAVORABLE" else (0.5 if outcome == "MIXED" else 0.0)
        resolution_days_raw = r.get("resolution_days")
        resolution_days = float(resolution_days_raw) if pd.notna(resolution_days_raw) else None

        for p in pros:
            pros_rows.append({"prosecutor": p, "judge": judge, "crime": crime})

        for a in atts:
            attorney_rows.append(
                {
                    "attorney": a,
                    "judge": judge,
                    "crime": crime,
                    "representation": rep,
                    "outcome": outcome,
                    "favorable_score": favorable_score,
                    "resolution_days": resolution_days,
                }
            )

    pros_df = pd.DataFrame(pros_rows) if pros_rows else pd.DataFrame(columns=["prosecutor", "judge", "crime"])
    attorney_df = (
        pd.DataFrame(attorney_rows)
        if attorney_rows
        else pd.DataFrame(columns=["attorney", "judge", "crime", "representation", "outcome", "favorable_score", "resolution_days"])
    )

    if pros_df.empty:
        pros_load = pd.DataFrame(columns=["prosecutor", "case_count", "unique_judges", "dominant_crime"])
        pros_crime = pd.DataFrame(columns=["prosecutor", "crime", "case_count"])
        prosecutor_metrics = pd.DataFrame(
            columns=[
                "prosecutor",
                "case_count",
                "dismissal_rate",
                "conviction_related_share",
                "avg_case_complexity",
            ]
        )
        prosecutor_concentration = pd.DataFrame(
            columns=[
                "crime",
                "total_cases",
                "unique_prosecutors",
                "top_prosecutor",
                "top_prosecutor_cases",
                "top_prosecutor_share_pct",
                "hhi",
                "effective_prosecutors",
            ]
        )
    else:
        pros_load = (
            pros_df.groupby("prosecutor", dropna=False)
            .agg(case_count=("judge", "count"), unique_judges=("judge", "nunique"))
            .reset_index()
            .sort_values("case_count", ascending=False)
        )
        dominant = (
            pros_df.groupby(["prosecutor", "crime"], dropna=False)
            .size()
            .reset_index(name="n")
            .sort_values(["prosecutor", "n"], ascending=[True, False])
            .drop_duplicates("prosecutor")
            [["prosecutor", "crime"]]
            .rename(columns={"crime": "dominant_crime"})
        )
        pros_load = pros_load.merge(dominant, on="prosecutor", how="left")
        pros_crime = (
            pros_df.groupby(["prosecutor", "crime"], dropna=False)
            .size()
            .reset_index(name="case_count")
            .sort_values("case_count", ascending=False)
        )

        prosecutor_case_rows: List[Dict[str, object]] = []
        for _, r in work.iterrows():
            case_prosecutors = _split_semicolon_scalar(str(r.get("prosecutors", "") or ""))
            complexity_score = float(r.get("charge_count", 0) or 0) + (float(r.get("docket_count", 0) or 0) / 10.0)
            for p in case_prosecutors:
                prosecutor_case_rows.append(
                    {
                        "prosecutor": p,
                        "dismissal_flag": bool(r.get("dismissal_flag", False)),
                        "conviction_related_flag": bool(r.get("conviction_related_flag", False)),
                        "complexity_score": complexity_score,
                    }
                )

        prosecutor_metrics = pd.DataFrame(
            columns=["prosecutor", "case_count", "dismissal_rate", "conviction_related_share", "avg_case_complexity"]
        )
        if prosecutor_case_rows:
            pcm = pd.DataFrame(prosecutor_case_rows)
            prosecutor_metrics = (
                pcm.groupby("prosecutor", dropna=False)
                .agg(
                    case_count=("prosecutor", "count"),
                    dismissal_rate=("dismissal_flag", "mean"),
                    conviction_related_share=("conviction_related_flag", "mean"),
                    avg_case_complexity=("complexity_score", "mean"),
                )
                .reset_index()
                .sort_values("case_count", ascending=False)
            )
            prosecutor_metrics["dismissal_rate"] = (prosecutor_metrics["dismissal_rate"] * 100).round(1)
            prosecutor_metrics["conviction_related_share"] = (prosecutor_metrics["conviction_related_share"] * 100).round(1)
            prosecutor_metrics["avg_case_complexity"] = prosecutor_metrics["avg_case_complexity"].round(2)

        prosecutor_concentration = (
            pros_crime.groupby("crime", dropna=False)
            .apply(
                lambda g: pd.Series(
                    {
                        "total_cases": int(g["case_count"].sum()),
                        "unique_prosecutors": int(g["prosecutor"].replace("", pd.NA).dropna().nunique()),
                        "top_prosecutor": str(g.sort_values("case_count", ascending=False).iloc[0]["prosecutor"] or ""),
                        "top_prosecutor_cases": int(g["case_count"].max()),
                        "top_prosecutor_share_pct": round(float(g["case_count"].max() / max(1, g["case_count"].sum()) * 100), 1),
                        "hhi": round(float(((g["case_count"] / max(1, g["case_count"].sum())) ** 2).sum()), 4),
                    }
                )
            )
            .reset_index()
            .sort_values("hhi", ascending=False)
        )
        prosecutor_concentration["effective_prosecutors"] = prosecutor_concentration["hhi"].apply(
            lambda x: round((1.0 / x), 2) if x and x > 0 else 0.0
        )

    if attorney_df.empty:
        attorney_load = pd.DataFrame(
            columns=[
                "attorney",
                "case_count",
                "unique_judges",
                "dominant_crime",
                "indigent_share",
                "paying_share",
                "favorable_outcome_rate",
                "avg_time_to_resolution_days",
                "resolved_cases",
            ]
        )
        attorney_crime = pd.DataFrame(columns=["attorney", "crime", "case_count"])
    else:
        attorney_load = (
            attorney_df.groupby("attorney", dropna=False)
            .agg(case_count=("judge", "count"), unique_judges=("judge", "nunique"))
            .reset_index()
            .sort_values("case_count", ascending=False)
        )
        dominant = (
            attorney_df.groupby(["attorney", "crime"], dropna=False)
            .size()
            .reset_index(name="n")
            .sort_values(["attorney", "n"], ascending=[True, False])
            .drop_duplicates("attorney")
            [["attorney", "crime"]]
            .rename(columns={"crime": "dominant_crime"})
        )
        indigent_share = (
            attorney_df.assign(is_indigent=attorney_df["representation"].eq("INDIGENT").astype(float))
            .groupby("attorney", dropna=False)["is_indigent"]
            .mean()
            .reset_index(name="indigent_share")
        )
        indigent_share["indigent_share"] = (indigent_share["indigent_share"] * 100).round(1)

        paying_share = (
            attorney_df.assign(is_paying=attorney_df["representation"].eq("PAYING").astype(float))
            .groupby("attorney", dropna=False)["is_paying"]
            .mean()
            .reset_index(name="paying_share")
        )
        paying_share["paying_share"] = (paying_share["paying_share"] * 100).round(1)

        resolved = attorney_df[attorney_df["outcome"].isin(["FAVORABLE", "UNFAVORABLE", "MIXED"])]
        if resolved.empty:
            favorable_rates = pd.DataFrame(columns=["attorney", "favorable_outcome_rate", "resolved_cases"])
            resolution_time = pd.DataFrame(columns=["attorney", "avg_time_to_resolution_days"])
        else:
            favorable_rates = (
                resolved.groupby("attorney", dropna=False)
                .agg(
                    favorable_outcome_rate=("favorable_score", "mean"),
                    resolved_cases=("outcome", "count"),
                )
                .reset_index()
            )
            favorable_rates["favorable_outcome_rate"] = (favorable_rates["favorable_outcome_rate"] * 100).round(1)

            resolution_time = (
                resolved.dropna(subset=["resolution_days"])
                .groupby("attorney", dropna=False)["resolution_days"]
                .mean()
                .reset_index(name="avg_time_to_resolution_days")
            )
            resolution_time["avg_time_to_resolution_days"] = resolution_time["avg_time_to_resolution_days"].round(1)

        attorney_load = (
            attorney_load.merge(dominant, on="attorney", how="left")
            .merge(indigent_share, on="attorney", how="left")
            .merge(paying_share, on="attorney", how="left")
            .merge(favorable_rates, on="attorney", how="left")
            .merge(resolution_time, on="attorney", how="left")
        )

        attorney_load["indigent_share"] = attorney_load["indigent_share"].fillna(0.0)
        attorney_load["paying_share"] = attorney_load["paying_share"].fillna(0.0)
        attorney_load["favorable_outcome_rate"] = attorney_load["favorable_outcome_rate"].fillna(0.0)
        attorney_load["avg_time_to_resolution_days"] = attorney_load["avg_time_to_resolution_days"].fillna(0.0)
        attorney_load["resolved_cases"] = attorney_load["resolved_cases"].fillna(0).astype(int)

        attorney_crime = (
            attorney_df.groupby(["attorney", "crime"], dropna=False)
            .size()
            .reset_index(name="case_count")
            .sort_values("case_count", ascending=False)
        )

    judge_crime = _exploded_links(work.rename(columns={"primary_crime_type": "crime"}), "judge", "crime")
    pros_judge = _exploded_links(work, "prosecutors", "judge")
    pros_judge = pros_judge.rename(columns={"prosecutors": "prosecutor"})

    pending_mask = work["outcome_bucket"].eq("UNKNOWN") | work["status"].apply(_is_pending_status)
    pending = work[pending_mask].copy()
    pending["age_bucket"] = pd.cut(
        pending["pending_age_days"].fillna(0),
        bins=[-1, 30, 90, 180, 365, 100000],
        labels=["0-30", "31-90", "91-180", "181-365", "366+"],
    )
    pending["age_bucket"] = pending["age_bucket"].astype(str).replace("nan", "UNKNOWN")
    age_order = ["0-30", "31-90", "91-180", "181-365", "366+", "UNKNOWN"]
    pending["age_bucket"] = pd.Categorical(pending["age_bucket"], categories=age_order, ordered=True)
    backlog_buckets = (
        pending.groupby("age_bucket", dropna=False)
        .size()
        .reset_index(name="case_count")
        .sort_values("age_bucket")
    )

    total_rows = max(1, len(work))
    completeness_rules = [
        ("judge", work["judge"].astype(str).str.strip().ne("")),
        ("status", work["status"].astype(str).str.strip().ne("")),
        ("defendant", work["defendant"].astype(str).str.strip().ne("")),
        ("prosecutors", work["prosecutors"].astype(str).str.strip().ne("")),
        ("attorneys", work["attorneys"].astype(str).str.strip().ne("")),
        ("primary_crime_type_known", work["primary_crime_type"].astype(str).ne("UNKNOWN")),
        ("charge_count_positive", pd.to_numeric(work["charge_count"], errors="coerce").fillna(0).gt(0)),
        ("outcome_bucket_known", work["outcome_bucket"].astype(str).ne("UNKNOWN")),
        ("resolution_days", pd.to_numeric(work["resolution_days"], errors="coerce").notna()),
        ("case_start_date", work["case_start_date"].astype(str).str.strip().ne("")),
    ]
    completeness_rows: List[Dict[str, object]] = []
    for field_name, mask in completeness_rules:
        present = int(mask.sum())
        missing = int(total_rows - present)
        completeness_rows.append(
            {
                "field": field_name,
                "present": present,
                "missing": missing,
                "completeness_pct": round((present / total_rows) * 100, 2),
            }
        )
    field_completeness = pd.DataFrame(completeness_rows).sort_values("completeness_pct")

    return {
        "base": work,
        "new_cases": new_cases,
        "crime_counts": crime_counts,
        "crime_by_year": crime_by_year,
        "crime_mom": crime_mom,
        "judge_concentration": judge_concentration,
        "prosecutor_concentration": prosecutor_concentration,
        "judge_metrics": judge_metrics,
        "prosecutor_metrics": prosecutor_metrics,
        "backlog_buckets": backlog_buckets,
        "field_completeness": field_completeness,
        "judge_load": judge_load,
        "pros_load": pros_load,
        "attorney_load": attorney_load,
        "judge_crime": judge_crime,
        "pros_crime": pros_crime,
        "attorney_crime": attorney_crime,
        "pros_judge": pros_judge,
    }


def render_overall_stats() -> None:
    st.subheader("Overall Stats")
    frames = build_overall_stat_frames()
    base = frames["base"]
    if base.empty:
        st.info("No data available for overall stats yet.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Cases", f"{len(base):,}")
    c2.metric("Unique Judges", f"{base['judge'].replace('', pd.NA).dropna().nunique():,}")
    c3.metric("Unique Prosecutors", f"{_split_semicolon_values(base['prosecutors']).__len__():,}")
    c4.metric("Unique Defense Attorneys", f"{_split_semicolon_values(base['attorneys']).__len__():,}")

    rep = (
        base.groupby("representation_bucket", dropna=False)
        .size()
        .reset_index(name="case_count")
        .sort_values("case_count", ascending=False)
    )
    rep["pct"] = (rep["case_count"] / rep["case_count"].sum() * 100).round(1)

    assigned_vs_hired = pd.DataFrame(
        [
            {
                "category": "Assigned (Public Defender)",
                "case_count": int((base["public_defender_count"] > 0).sum()),
            },
            {
                "category": "Hired (Retained)",
                "case_count": int((base["retained_count"] > 0).sum()),
            },
        ]
    )
    assigned_vs_hired["pct"] = (
        assigned_vs_hired["case_count"] / max(1, int(len(base))) * 100
    ).round(1)

    left, right = st.columns(2)
    left.markdown("### Indigent vs Paying Defendants")
    left.dataframe(rep, width="stretch")

    right.markdown("### Crime Types with Counts")
    right.dataframe(frames["crime_counts"], width="stretch")

    st.markdown("### Assigned Attorney vs Hired Attorney")
    st.dataframe(assigned_vs_hired, width="stretch")

    st.markdown("### New Cases Over Time")
    new_cases = frames["new_cases"]
    if not new_cases.empty:
        new_by_year = new_cases.groupby("year", dropna=False)["case_count"].sum().reset_index()
        st.bar_chart(new_by_year.set_index("year"))
        st.dataframe(_top_k(new_cases.sort_values(["year", "scraped_month"], ascending=[False, False]), 36), width="stretch")

    st.markdown("### Trending Crimes (Year x Crime Type)")
    crime_by_year = frames["crime_by_year"]
    if not crime_by_year.empty:
        pivot = crime_by_year.pivot(index="year", columns="primary_crime_type", values="case_count").fillna(0)
        st.bar_chart(pivot)
    st.dataframe(_top_k(crime_by_year, 80), width="stretch")

    st.markdown("### Crime Types Month-over-Month Trend")
    crime_mom = frames["crime_mom"]
    if not crime_mom.empty:
        mom_pivot = crime_mom.pivot(index="scraped_month", columns="primary_crime_type", values="case_count").fillna(0)
        st.line_chart(mom_pivot)
    st.dataframe(_top_k(crime_mom.sort_values(["scraped_month", "case_count"], ascending=[False, False]), 120), width="stretch")

    st.markdown("### Judge Concentration Index by Crime Type")
    st.dataframe(_top_k(frames["judge_concentration"], 100), width="stretch")

    st.markdown("### Prosecutor Concentration Index by Crime Type")
    st.dataframe(_top_k(frames["prosecutor_concentration"], 100), width="stretch")

    st.markdown("### Judges: Median Charges, Disposition Speed, Plea-vs-Trial Split")
    st.dataframe(_top_k(frames["judge_metrics"], 80), width="stretch")

    st.markdown("### Prosecutors: Dismissal, Conviction Share, Case Complexity")
    st.dataframe(_top_k(frames["prosecutor_metrics"], 80), width="stretch")

    st.markdown("### System Backlog (Pending Age Buckets)")
    backlog = frames["backlog_buckets"]
    if not backlog.empty:
        st.bar_chart(backlog.set_index("age_bucket"))
    st.dataframe(backlog, width="stretch")

    st.markdown("### Data Quality Alerts (Field Completeness)")
    st.dataframe(frames["field_completeness"], width="stretch")

    st.markdown("### Judges Caseload")
    st.dataframe(_top_k(frames["judge_load"], 40), width="stretch")

    st.markdown("### Prosecutors: Assignments and Workload")
    st.dataframe(_top_k(frames["pros_load"], 60), width="stretch")

    st.markdown("### Defense Attorneys: Client Mix, Favorable Outcome Rate, Time-to-Resolution")
    st.dataframe(_top_k(frames["attorney_load"], 60), width="stretch")

    st.markdown("### Which Judges Get What Kind of Cases")
    st.dataframe(_top_k(frames["judge_crime"], 100), width="stretch")

    st.markdown("### Which Judges Get Which Prosecutors")
    st.dataframe(_top_k(frames["pros_judge"], 100), width="stretch")

    st.markdown("### Which Prosecutors Get Which Crime Types")
    st.dataframe(_top_k(frames["pros_crime"], 100), width="stretch")

    st.markdown("### Which Attorneys Get Which Crime Types")
    st.dataframe(_top_k(frames["attorney_crime"], 100), width="stretch")

    with st.expander("Suggested Next Stats by Group"):
        st.markdown(
            "\n".join(
                [
                    "- Judges: median charges per case, disposition speed, plea-vs-trial split.",
                    "- Prosecutors: dismissal rate, conviction-related disposition share, average case complexity.",
                    "- Defense Attorneys: client mix (indigent vs paying), favorable-outcome rate, time-to-resolution.",
                    "- Crime Types: month-over-month trend, judge concentration index, prosecutor concentration index.",
                    "- System-Level: backlog (pending age buckets), data-quality alerts by field completeness.",
                ]
            )
        )


def render_overview() -> None:
    inventory = collect_file_inventory()
    latest = latest_per_case(inventory)
    gaps = gap_stats(latest)
    failed = failed_latest_cases(latest)
    state = load_state()

    st.subheader("Overview")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total JSON Files", f"{len(inventory):,}")
    c2.metric("Latest Unique Cases", f"{len(latest):,}")
    c3.metric("Latest Failed Cases", f"{len(failed):,}")
    c4.metric("Retry Queue Items", f"{sum(len(v) for v in (state.get('retry_queue') or {}).values()):,}")

    st.caption(
        f"last_run={state.get('last_run')} | cooldown_until={state.get('cooldown_until')} | consecutive_errors={state.get('consecutive_errors')}"
    )

    if not latest.empty:
        by_year = latest.groupby("year").size().reset_index(name="latest_cases")
        st.write("Latest cases by year")
        st.bar_chart(by_year.set_index("year"))

    if not gaps.empty:
        st.write("Gap density by year")
        st.dataframe(gaps, width="stretch")


def render_retry_queue() -> None:
    state = load_state()
    rq = state.get("retry_queue") or {}
    st.subheader("Retry Queue")
    rows = []
    for y, nums in rq.items():
        if not isinstance(nums, list):
            continue
        try:
            year = int(y)
        except ValueError:
            continue
        rows.append({"year": year, "queued_count": len(nums), "sample": ", ".join(str(n) for n in sorted(nums)[:20])})
    if rows:
        df = pd.DataFrame(rows).sort_values("year")
        st.dataframe(df, width="stretch")
    else:
        st.info("Retry queue is empty.")


def render_errors() -> None:
    inventory = collect_file_inventory()
    latest = latest_per_case(inventory)
    failed = failed_latest_cases(latest)

    st.subheader("Latest Failures / Errors")
    if failed.empty:
        st.success("No failed latest snapshots detected.")
        return

    year_filter = st.multiselect("Filter years", sorted(failed["year"].unique().tolist()), default=sorted(failed["year"].unique().tolist()))
    show = failed[failed["year"].isin(year_filter)] if year_filter else failed
    st.dataframe(show, width="stretch")


def render_alerts() -> None:
    st.subheader("Change Alerts")
    alerts = load_alerts()
    if alerts.empty:
        st.info("No alert entries yet. Alerts are written by daily_streams to logs/case_change_alerts.log")
    else:
        st.dataframe(alerts.iloc[::-1], width="stretch")

    st.subheader("Scheduled Query Alerts")
    q_alerts = load_query_alerts()
    if q_alerts.empty:
        st.info("No scheduled query alerts yet. They are written to logs/query_alerts.log")
    else:
        st.dataframe(q_alerts.iloc[::-1], width="stretch")


def render_query_lab() -> None:
    st.subheader("Query, Group, Filter")

    df = build_latest_dataset()
    if df.empty:
        st.warning("No latest case data found.")
        return

    years = sorted(df["year"].unique().tolist())
    judge_options = sorted(_non_empty_unique(df["judge"].fillna("").astype(str).tolist()))
    status_options = sorted(_non_empty_unique(df["status"].fillna("").astype(str).tolist()))
    prosecutor_options = sorted(_split_semicolon_values(df["prosecutors"]))
    attorney_options = sorted(_split_semicolon_values(df["all_attorneys"]))

    with st.form("query_form"):
        col1, col2 = st.columns(2)
        q_years = col1.multiselect("Years", years, default=years)
        q_judge_selected = col2.multiselect("Judge quick select", judge_options, default=[])
        q_judge = col2.text_input("Judge contains (free text)", value="")

        col3, col4 = st.columns(2)
        q_status_selected = col3.multiselect("Status quick select", status_options, default=[])
        q_status = col3.text_input("Status contains (free text)", value="")
        q_defendant = col4.text_input("Defendant contains", value="")

        col5, col6 = st.columns(2)
        q_pros_selected = col5.multiselect("Prosecutor quick select", prosecutor_options, default=[])
        q_pros = col5.text_input("Prosecutor contains (free text)", value="")
        q_att_selected = col6.multiselect("Attorney quick select", attorney_options, default=[])
        q_att = col6.text_input("Attorney contains (free text)", value="")

        q_only_existing = st.checkbox("Only exists=true", value=False)
        group_by = st.multiselect(
            "Group by",
            ["year", "judge", "status", "prosecutors", "attorneys"],
            default=[],
        )

        submitted = st.form_submit_button("Run Query")

    if submitted:
        result = run_query(
            df,
            years=q_years,
            judge_contains=q_judge,
            judge_selected=q_judge_selected,
            status_contains=q_status,
            status_selected=q_status_selected,
            defendant_contains=q_defendant,
            prosecutor_contains=q_pros,
            prosecutor_selected=q_pros_selected,
            attorney_contains=q_att,
            attorney_selected=q_att_selected,
            only_existing=q_only_existing,
            group_by=group_by,
        )

        st.caption(f"Result rows: {len(result.rows)}")
        st.dataframe(result.rows, width="stretch")

        if not result.grouped.empty:
            st.caption("Grouped output")
            st.dataframe(result.grouped, width="stretch")

        st.markdown("### Save As Scheduled Query")
        with st.form("save_query_job_form"):
            job_name = st.text_input("Job name", value="New query alert")
            interval = st.number_input("Run every N minutes", min_value=1, max_value=1440, value=60)
            cond_op = st.selectbox("Alert when row_count", [">=", ">", "==", "<=", "<"], index=0)
            cond_val = st.number_input("Threshold value", min_value=0, value=1)
            enable_job = st.checkbox("Enabled", value=True)
            save_job_btn = st.form_submit_button("Save Job")

        if save_job_btn:
            jobs = load_jobs()
            jid = f"job-{uuid.uuid4().hex[:8]}"
            jobs.append(
                {
                    "id": jid,
                    "name": job_name.strip() or jid,
                    "enabled": bool(enable_job),
                    "interval_minutes": int(interval),
                    "query": {
                        "years": [int(y) for y in q_years],
                        "judge_contains": q_judge,
                        "judge_selected": list(q_judge_selected),
                        "status_contains": q_status,
                        "status_selected": list(q_status_selected),
                        "defendant_contains": q_defendant,
                        "prosecutor_contains": q_pros,
                        "prosecutor_selected": list(q_pros_selected),
                        "attorney_contains": q_att,
                        "attorney_selected": list(q_att_selected),
                        "only_existing": bool(q_only_existing),
                        "group_by": list(group_by),
                    },
                    "alert_condition": {
                        "op": cond_op,
                        "value": int(cond_val),
                    },
                }
            )
            save_jobs(jobs)
            st.success(f"Saved scheduled job: {jid}")


def render_scheduled_jobs() -> None:
    st.subheader("Scheduled Query Jobs")

    jobs = load_jobs()
    state = load_job_state()
    last_runs = state.get("last_runs", {}) if isinstance(state, dict) else {}

    if not jobs:
        st.info("No scheduled query jobs configured yet.")
        return

    rows = []
    for j in jobs:
        jid = str(j.get("id", ""))
        rows.append(
            {
                "id": jid,
                "name": j.get("name", ""),
                "enabled": bool(j.get("enabled", True)),
                "interval_minutes": int(j.get("interval_minutes", 60)),
                "last_run": (last_runs or {}).get(jid, ""),
                "condition": j.get("alert_condition", {}),
            }
        )

    st.dataframe(pd.DataFrame(rows), width="stretch")

    ids = [str(j.get("id", "")) for j in jobs]
    selected = st.selectbox("Select job", ids)
    target = next((j for j in jobs if str(j.get("id")) == selected), None)
    if not target:
        return

    col1, col2, col3 = st.columns(3)
    if col1.button("Run selected now"):
        df = build_latest_dataset()
        result = run_job_once(df, target)
        st.success(
            f"Ran {result['job_name']} rows={result['rows']} triggered={result['triggered']}"
        )

    if col2.button("Toggle enable/disable"):
        target["enabled"] = not bool(target.get("enabled", True))
        save_jobs(jobs)
        st.success(f"Updated enabled={target['enabled']} for {selected}")

    if col3.button("Delete selected"):
        new_jobs = [j for j in jobs if str(j.get("id")) != selected]
        save_jobs(new_jobs)
        st.success(f"Deleted {selected}")


def render_case_explorer() -> None:
    st.subheader("Case History Explorer")
    col1, col2 = st.columns(2)
    year = col1.number_input("Year", min_value=2020, max_value=2035, value=2026, step=1)
    number = col2.number_input("Case Number", min_value=1, max_value=999999, value=711292, step=1)

    hist = case_history(int(year), int(number))
    if hist.empty:
        st.warning("No snapshots found for this case.")
        return

    st.dataframe(hist, width="stretch")

    distinct = hist["hash"].nunique(dropna=True)
    st.caption(f"Snapshots: {len(hist)} | Distinct payload hashes: {distinct}")
    if distinct > 1:
        st.error("Case changed across snapshots (distinct payload hashes detected).")
    else:
        st.success("No substantive payload changes detected across snapshots.")


def main() -> None:
    st.set_page_config(page_title="Cuyahoga Scraper Ops Dashboard", layout="wide")
    st.title("Cuyahoga Scraper Ops Dashboard")
    st.caption("Interactive monitoring for gaps, retries, errors, and case changes.")

    tabs = st.tabs([
        "Overview",
        "Overall Stats",
        "Retry Queue",
        "Errors",
        "Alerts",
        "Case Explorer",
        "Query Lab",
        "Scheduled Jobs",
    ])

    with tabs[0]:
        render_overview()
    with tabs[1]:
        render_overall_stats()
    with tabs[2]:
        render_retry_queue()
    with tabs[3]:
        render_errors()
    with tabs[4]:
        render_alerts()
    with tabs[5]:
        render_case_explorer()
    with tabs[6]:
        render_query_lab()
    with tabs[7]:
        render_scheduled_jobs()


if __name__ == "__main__":
    main()
