#!/usr/bin/env python3
"""Build compact case/defendant relationship data for docs/foxxiie."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "foxxiie"
YEARS = {2023, 2024, 2025, 2026}


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return "" if text.upper() in {"N/A", "NONE", "NULL"} else text


def key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", clean(value).upper()).strip()


def case_id_from(path: Path, data: dict[str, Any]) -> str:
    meta = data.get("metadata") or {}
    summary = data.get("summary") or {}
    found = clean(meta.get("case_id") or summary.get("case_id"))
    if found:
        return found.upper()
    match = re.search(r"(\d{4})-(\d{6})", path.name)
    if not match:
        return path.stem.upper()
    year, number = match.groups()
    return f"CR-{year[-2:]}-{number}-A"


def case_year(case_id: str, data: dict[str, Any]) -> int | None:
    meta = data.get("metadata") or {}
    year = meta.get("year") or meta.get("case_year")
    try:
        return int(year)
    except Exception:
        match = re.search(r"CR-(\d{2})-", case_id)
        return 2000 + int(match.group(1)) if match else None


def defendant_name(data: dict[str, Any]) -> str:
    defendant = data.get("defendant")
    if isinstance(defendant, dict):
        direct = clean(defendant.get("Name:") or defendant.get("Name"))
        if direct:
            return direct
        for value in defendant.values():
            text = clean(value)
            match = re.search(r"\bvs\.\s+(.+)$", text, re.I)
            if match:
                return clean(match.group(1))
    fields = ((data.get("summary") or {}).get("fields") or {})
    direct = clean(fields.get("Name:") or fields.get("Name"))
    if direct:
        return direct
    for value in fields.values():
        text = clean(value)
        match = re.search(r"\bvs\.\s+(.+)$", text, re.I)
        if match:
            return clean(match.group(1))
    return ""


def current_judge(data: dict[str, Any]) -> str:
    summary = data.get("summary") or {}
    fields = summary.get("fields") or {}
    return clean(summary.get("current_judge") or fields.get("Judge Name:") or fields.get("Judge Name"))


def attorney_names(data: dict[str, Any], party: str) -> list[str]:
    names: list[str] = []
    for attorney in data.get("attorneys") or []:
        if not isinstance(attorney, dict):
            continue
        name = clean(attorney.get("name"))
        if not name:
            continue
        attorney_party = clean(attorney.get("party")).lower()
        role = clean(attorney.get("role")).lower()
        office = clean(attorney.get("office"))
        if party == "defense" and ("defense" in attorney_party or "defense" in role):
            names.append(name)
        elif party == "prosecution" and (
            "prosecution" in attorney_party
            or "prosecut" in role
            or "prosecut" in name.lower()
            or "prosecut" in office.lower()
        ):
            names.append(name)
    return sorted(set(names), key=str.upper)


def docket_prosecutors(data: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    patterns = [
        re.compile(r"PROSECUTOR(?:\(S\))?\s+([A-Z][A-Z .'-]{3,80}?)\s+PRESENT\b"),
        re.compile(r"ASSISTANT COUNTY PROSECUTOR\s+([A-Z][A-Z .'-]{3,80}?)(?:\s+PRESENT|\s+APPEARED|\s+FILED|\.)"),
    ]
    for entry in data.get("docket") or []:
        if not isinstance(entry, dict):
            continue
        text = clean(entry.get("description")).upper()
        for pattern in patterns:
            for match in pattern.finditer(text):
                name = clean(match.group(1).strip(" .,'-"))
                if name and "PROSECUTOR" not in name and "STATE" not in name:
                    names.add(name)
    return sorted(names)


def charge_summary(data: dict[str, Any]) -> list[str]:
    charges: list[str] = []
    for charge in ((data.get("summary") or {}).get("charges") or data.get("charges") or []):
        if not isinstance(charge, dict):
            continue
        desc = clean(charge.get("charge_description") or charge.get("description") or charge.get("Charge Description"))
        if desc:
            charges.append(desc)
    return sorted(set(charges), key=str.upper)[:4]


def status(data: dict[str, Any]) -> str:
    outcome = data.get("outcome") or {}
    fields = ((data.get("summary") or {}).get("fields") or {})
    return clean(outcome.get("final_status") or fields.get("Status:") or fields.get("Status"))


def latest_date(data: dict[str, Any]) -> str:
    meta = data.get("metadata") or {}
    return clean(meta.get("latest_case_update_date") or meta.get("case_started_date") or meta.get("scraped_at"))[:10]


def build() -> dict[str, Any]:
    latest_by_case: dict[str, tuple[str, Path, dict[str, Any]]] = {}
    for year in YEARS:
        for path in (ROOT / "out" / str(year)).glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            cid = case_id_from(path, data)
            stamp = clean((data.get("metadata") or {}).get("downloaded_at") or (data.get("metadata") or {}).get("scraped_at"))
            previous = latest_by_case.get(cid)
            if previous is None or stamp > previous[0]:
                latest_by_case[cid] = (stamp, path, data)

    cases: list[dict[str, Any]] = []
    defendants: dict[str, dict[str, Any]] = {}
    for cid, (_, _path, data) in latest_by_case.items():
        year = case_year(cid, data)
        if year not in YEARS:
            continue
        defendant = defendant_name(data)
        defendant_key = key(defendant)
        judge = current_judge(data)
        defense = attorney_names(data, "defense")
        prosecutors = sorted(set(attorney_names(data, "prosecution") + docket_prosecutors(data)), key=str.upper)
        record = {
            "id": cid,
            "year": year,
            "status": status(data),
            "updated": latest_date(data),
            "judge": judge,
            "defendant": defendant,
            "defendant_key": defendant_key,
            "attorneys": defense,
            "prosecutors": prosecutors,
            "charges": charge_summary(data),
        }
        cases.append(record)
        if defendant_key:
            item = defendants.setdefault(defendant_key, {
                "key": defendant_key,
                "name": defendant,
                "cases": [],
                "judges": set(),
                "attorneys": set(),
                "prosecutors": set(),
            })
            item["cases"].append(cid)
            if judge:
                item["judges"].add(judge)
            item["attorneys"].update(defense)
            item["prosecutors"].update(prosecutors)

    cases.sort(key=lambda x: (x.get("year") or 0, x.get("id") or ""), reverse=True)
    defendant_rows = []
    for item in defendants.values():
        defendant_rows.append({
            "key": item["key"],
            "name": item["name"],
            "case_count": len(item["cases"]),
            "cases": sorted(item["cases"], reverse=True),
            "judges": sorted(item["judges"]),
            "attorneys": sorted(item["attorneys"]),
            "prosecutors": sorted(item["prosecutors"]),
        })
    defendant_rows.sort(key=lambda x: (-x["case_count"], x["name"]))

    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "totals": {
            "cases": len(cases),
            "defendants": len(defendant_rows),
        },
        "cases": cases,
        "defendants": defendant_rows,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "graph.json"
    payload = build()
    out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out_path} - build_foxxiie_graph.py:228")
    print(f"Cases:      {payload['totals']['cases']} - build_foxxiie_graph.py:229")
    print(f"Defendants: {payload['totals']['defendants']} - build_foxxiie_graph.py:230")


if __name__ == "__main__":
    main()
