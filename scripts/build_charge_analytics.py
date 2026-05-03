#!/usr/bin/env python3
"""Build charge frequency and grouping analytics from scraped case JSON."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
YEARS = (2023, 2024, 2025, 2026)
OUT_DIR = ROOT / "analysis_output" / "charge_analytics"


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return "" if text.upper() in {"", "N/A", "NONE", "NULL"} else text


def norm_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", clean(value).upper()).strip()


def latest_files() -> dict[str, Path]:
    latest: dict[str, tuple[str, Path]] = {}
    for year in YEARS:
        for path in (ROOT / "out" / str(year)).glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            meta = data.get("metadata") or {}
            summary = data.get("summary") or {}
            case_id = clean(meta.get("case_id") or summary.get("case_id"))
            if not case_id:
                match = re.search(r"(\d{4})-(\d{6})", path.name)
                if not match:
                    continue
                file_year, number = match.groups()
                case_id = f"CR-{file_year[-2:]}-{number}-A"
            stamp = clean(meta.get("downloaded_at") or meta.get("scraped_at") or path.name)
            previous = latest.get(case_id)
            if previous is None or stamp > previous[0]:
                latest[case_id] = (stamp, path)
    return {case_id: path for case_id, (_stamp, path) in latest.items()}


def parse_embedded_charge_rows(fields: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for value in fields.values():
        if not isinstance(value, dict):
            continue
        if clean(value.get("format")).lower() != "csv":
            continue
        data = clean(value.get("data"))
        if not data:
            continue
        reader = csv.DictReader(data.splitlines())
        names = {clean(name).lower() for name in (reader.fieldnames or [])}
        if "statute" not in names or not ({"charge description", "charge_description", "description"} & names):
            continue
        for row in reader:
            desc = clean(row.get("Charge Description") or row.get("charge_description") or row.get("Description") or row.get("description"))
            statute = clean(row.get("Statute") or row.get("statute"))
            disposition = clean(row.get("Disposition") or row.get("disposition"))
            if desc:
                rows.append({"description": desc, "statute": statute, "disposition": disposition})
    return rows


def extract_charges(data: dict[str, Any]) -> list[dict[str, str]]:
    summary = data.get("summary") or {}
    fields = summary.get("fields") or {}
    rows: list[dict[str, str]] = []
    for charge in summary.get("charges") or data.get("charges") or []:
        if not isinstance(charge, dict):
            continue
        desc = clean(charge.get("charge_description") or charge.get("description") or charge.get("Charge Description"))
        statute = clean(charge.get("statute") or charge.get("Statute"))
        disposition = clean(charge.get("disposition") or charge.get("Disposition"))
        if desc:
            rows.append({"description": desc, "statute": statute, "disposition": disposition})
    return rows or parse_embedded_charge_rows(fields if isinstance(fields, dict) else {})


TYPO_REPLACEMENTS = {
    "AGGREVATED": "AGGRAVATED",
    "AGGTAVATED": "AGGRAVATED",
    "AGG.": "AGGRAVATED",
    "AGG ": "AGGRAVATED ",
    "POSSESION": "POSSESSION",
    "OFFCER": "OFFICER",
    "OFFICER0": "OFFICER",
    "FACILTY": "FACILITY",
    "MARSHALL": "MARSHAL",
}


def canonical_charge(description: str) -> str:
    text = norm_key(description)
    for wrong, right in TYPO_REPLACEMENTS.items():
        text = text.replace(wrong, right)
    text = text.replace("THEFT AGGRAVATED THEFT", "THEFT")
    text = re.sub(r"^ATTEMPTED\s+", "ATTEMPTED, ", text)
    text = re.sub(r"\s+", " ", text).strip()
    variants = [
        (r"^DOMESTIC VIOLENCE.*", "DOMESTIC VIOLENCE"),
        (r"^ASSAULT.*FAMILY.*HOUSEHOLD.*", "ASSAULT - FAMILY/HOUSEHOLD"),
        (r"^ASSAULT.*PEACE OFFICER.*", "ASSAULT - PEACE OFFICER"),
        (r"^ASSAULT.*NURSE|^ASSAULT.*MEDIC|^ASSAULT.*HEALTH CARE|^ASSAULT.*EMERGENCY", "ASSAULT - HEALTH/EMERGENCY WORKER"),
        (r"^AGGRAVATED POSSESSION.*", "AGGRAVATED DRUG POSSESSION"),
        (r"^DRUG POSSESSION.*", "DRUG POSSESSION"),
        (r"^TRAFFICKING.*", "TRAFFICKING OFFENSE"),
        (r"^THEFT.*", "THEFT"),
        (r"^GRAND THEFT.*", "GRAND THEFT"),
        (r"^FELONIOUS ASSAULT.*", "FELONIOUS ASSAULT"),
        (r"^HAVING WEAPONS WHILE UNDER DISABILITY.*", "HAVING WEAPONS WHILE UNDER DISABILITY"),
        (r"^IMPROPERLY HANDLING FIREARMS.*", "IMPROPERLY HANDLING FIREARMS IN A MOTOR VEHICLE"),
        (r"^CARRYING CONCEALED WEAPON.*", "CARRYING CONCEALED WEAPONS"),
        (r"^FAILURE TO COMPLY.*", "FAILURE TO COMPLY"),
        (r"^ENDANGERING CHILDREN.*", "ENDANGERING CHILDREN"),
        (r"^RECEIVING STOLEN PROPERTY.*", "RECEIVING STOLEN PROPERTY"),
        (r"^POSSESSING CRIMINAL TOOLS.*", "POSSESSING CRIMINAL TOOLS"),
        (r"^OBSTRUCTING OFFICIAL BUSINESS.*", "OBSTRUCTING OFFICIAL BUSINESS"),
        (r"^DRIVING WHILE UNDER THE INFLUENCE.*", "OVI/DUI"),
    ]
    for pattern, replacement in variants:
        if re.search(pattern, text):
            return replacement
    return text


def charge_family(canonical: str, statute: str) -> str:
    text = f"{canonical} {statute}".upper()
    if any(x in text for x in ["DRUG", "TRAFFICKING", "COCAINE", "FENTANYL", "HEROIN", "MARIJUANA"]):
        return "Drug"
    if any(x in text for x in ["WEAPON", "FIREARM", "CONCEALED", "DISCHARGE OF FIREARM"]):
        return "Weapons"
    if any(x in text for x in ["DOMESTIC VIOLENCE", "STRANGULATION", "ENDANGERING CHILDREN", "MENACING"]):
        return "Domestic / family violence"
    if any(x in text for x in ["ASSAULT", "ROBBERY", "MURDER", "HOMICIDE", "KIDNAP", "ABDUCTION", "RAPE", "SEXUAL"]):
        return "Violent / person"
    if any(x in text for x in ["THEFT", "BURGLARY", "STOLEN", "VANDALISM", "DAMAGING", "FRAUD", "BREAKING AND ENTERING"]):
        return "Property / fraud"
    if any(x in text for x in ["OVI", "DUI", "FAILURE TO COMPLY", "VEHICLE", "UNAUTHORIZED USE"]):
        return "Traffic / vehicle"
    if any(x in text for x in ["OBSTRUCT", "TAMPERING", "RESISTING", "ESCAPE", "FUGITIVE"]):
        return "Court / law enforcement"
    return "Other"


def case_fields(data: dict[str, Any]) -> dict[str, str]:
    meta = data.get("metadata") or {}
    summary = data.get("summary") or {}
    fields = summary.get("fields") or {}
    attorneys = data.get("attorneys") or []
    defense: list[str] = []
    prosecution: list[str] = []
    for entry in attorneys:
        if not isinstance(entry, dict):
            continue
        name = clean(entry.get("name"))
        if not name:
            continue
        party = clean(entry.get("party")).upper()
        role = clean(entry.get("role")).upper()
        kind = clean(entry.get("type")).upper()
        if "PROSEC" in party or "PROSEC" in role or "STATE ATTORNEY" in kind or "PROSECUTOR" in name.upper():
            prosecution.append(name)
        else:
            defense.append(name)
    return {
        "year": str(meta.get("year") or meta.get("case_year") or ""),
        "judge": clean(summary.get("current_judge") or fields.get("Judge Name:")),
        "defendant": clean(fields.get("Name:") or (data.get("defendant") or {}).get("Name:") if isinstance(data.get("defendant"), dict) else ""),
        "status": clean(fields.get("Status:")),
        "defense_attorneys": "; ".join(sorted(set(defense))),
        "prosecutors": "; ".join(sorted(set(prosecution))),
    }


def increment_group(groups: dict[str, Counter], group_name: str, key: str, amount: int = 1) -> None:
    if group_name and key:
        groups[group_name][key] += amount


def top_items(counter: Counter, n: int = 25) -> list[dict[str, Any]]:
    return [{"name": key, "count": value} for key, value in counter.most_common(n)]


def bottom_items(counter: Counter, n: int = 25) -> list[dict[str, Any]]:
    return [{"name": key, "count": value} for key, value in sorted(counter.items(), key=lambda kv: (kv[1], kv[0]))[:n]]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_charge_instances = 0
    case_count = 0
    cases_with_charges = 0
    cases_without_charges = 0
    charge_instances = Counter()
    charge_cases: dict[str, set[str]] = defaultdict(set)
    raw_descriptions = Counter()
    statutes = Counter()
    families = Counter()
    family_cases: dict[str, set[str]] = defaultdict(set)
    by_year: dict[str, Counter] = defaultdict(Counter)
    by_family_year: dict[str, Counter] = defaultdict(Counter)
    by_judge_family: dict[str, Counter] = defaultdict(Counter)
    by_attorney_family: dict[str, Counter] = defaultdict(Counter)
    by_prosecutor_family: dict[str, Counter] = defaultdict(Counter)
    case_charge_counts = Counter()

    latest = latest_files()
    charge_rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    for case_id, path in latest.items():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        case_count += 1
        fields = case_fields(data)
        charges = extract_charges(data)
        valid_charges = []
        for charge in charges:
            desc = clean(charge.get("description"))
            if not desc:
                continue
            canon = canonical_charge(desc)
            statute = clean(charge.get("statute"))
            family = charge_family(canon, statute)
            valid_charges.append((desc, canon, statute, family, clean(charge.get("disposition"))))
        if valid_charges:
            cases_with_charges += 1
        else:
            cases_without_charges += 1
        case_charge_counts[len(valid_charges)] += 1
        case_rows.append({"case_id": case_id, "charge_count": len(valid_charges), **fields, "file": str(path.relative_to(ROOT))})
        seen_in_case: set[str] = set()
        seen_family_in_case: set[str] = set()
        for desc, canon, statute, family, disposition in valid_charges:
            raw_charge_instances += 1
            raw_descriptions[desc] += 1
            charge_instances[canon] += 1
            statutes[statute or "NO STATUTE"] += 1
            families[family] += 1
            by_year[fields["year"]][canon] += 1
            by_family_year[fields["year"]][family] += 1
            for judge in [fields["judge"]]:
                increment_group(by_judge_family, judge, family)
            for attorney in fields["defense_attorneys"].split("; "):
                increment_group(by_attorney_family, attorney, family)
            for prosecutor in fields["prosecutors"].split("; "):
                increment_group(by_prosecutor_family, prosecutor, family)
            if canon not in seen_in_case:
                charge_cases[canon].add(case_id)
                seen_in_case.add(canon)
            if family not in seen_family_in_case:
                family_cases[family].add(case_id)
                seen_family_in_case.add(family)
            charge_rows.append({
                "case_id": case_id,
                "year": fields["year"],
                "judge": fields["judge"],
                "defendant": fields["defendant"],
                "defense_attorneys": fields["defense_attorneys"],
                "prosecutors": fields["prosecutors"],
                "raw_description": desc,
                "canonical_charge": canon,
                "family": family,
                "statute": statute,
                "disposition": disposition,
                "file": str(path.relative_to(ROOT)),
            })

    canonical_rows = []
    for charge, instance_count in charge_instances.most_common():
        canonical_rows.append({
            "canonical_charge": charge,
            "charge_instances": instance_count,
            "case_count": len(charge_cases[charge]),
            "family": charge_family(charge, ""),
        })

    family_rows = []
    for family, instance_count in families.most_common():
        family_rows.append({
            "family": family,
            "charge_instances": instance_count,
            "case_count": len(family_cases[family]),
            "pct_charge_instances": round(instance_count / raw_charge_instances * 100, 2) if raw_charge_instances else 0,
            "pct_cases": round(len(family_cases[family]) / case_count * 100, 2) if case_count else 0,
        })

    summary = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "years": list(YEARS),
        "case_count": case_count,
        "cases_with_charges": cases_with_charges,
        "cases_without_charges": cases_without_charges,
        "charge_instances": raw_charge_instances,
        "unique_raw_descriptions": len(raw_descriptions),
        "unique_canonical_charges": len(charge_instances),
        "unique_statutes": len(statutes),
        "top_charges": top_items(charge_instances, 30),
        "least_common_charges": bottom_items(charge_instances, 30),
        "top_raw_descriptions": top_items(raw_descriptions, 30),
        "families": family_rows,
        "top_statutes": top_items(statutes, 30),
        "charge_count_distribution_per_case": [{"charge_count": key, "cases": value} for key, value in sorted(case_charge_counts.items())],
        "top_charges_by_year": {year: top_items(counter, 15) for year, counter in sorted(by_year.items())},
        "families_by_year": {year: top_items(counter, 12) for year, counter in sorted(by_family_year.items())},
        "top_judge_family_mix": {
            judge: top_items(counter, 6)
            for judge, counter in sorted(by_judge_family.items(), key=lambda kv: -sum(kv[1].values()))[:25]
        },
        "top_defense_attorney_family_mix": {
            attorney: top_items(counter, 6)
            for attorney, counter in sorted(by_attorney_family.items(), key=lambda kv: -sum(kv[1].values()))[:25]
        },
        "top_prosecutor_family_mix": {
            prosecutor: top_items(counter, 6)
            for prosecutor, counter in sorted(by_prosecutor_family.items(), key=lambda kv: -sum(kv[1].values()))[:25]
        },
    }

    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(OUT_DIR / "canonical_charges.csv", canonical_rows)
    write_csv(OUT_DIR / "families.csv", family_rows)
    write_csv(OUT_DIR / "charge_instances.csv", charge_rows)
    write_csv(OUT_DIR / "cases.csv", case_rows)
    print(f"Wrote {OUT_DIR}")
    print(f"Cases: {case_count:,}")
    print(f"Cases with charges: {cases_with_charges:,}")
    print(f"Charge instances: {raw_charge_instances:,}")
    print(f"Canonical charges: {len(charge_instances):,}")
    print("Top charges:")
    for row in canonical_rows[:15]:
        print(f"  {row['charge_instances']:>5,} charges / {row['case_count']:>5,} cases  {row['canonical_charge']}")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
