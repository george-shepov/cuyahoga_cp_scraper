from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.schemas.alerts import AlertEvent, AlertScanRequest, AlertScanResponse


@dataclass(frozen=True)
class AlertRule:
    code: str
    title: str
    category: str
    tier: str
    severity: str
    keywords_any: tuple[str, ...]
    keywords_all: tuple[str, ...] = ()
    killer: bool = False


RULES: tuple[AlertRule, ...] = (
    AlertRule("new_case_filed", "New case filed", "case_flow", "basic", "medium", ("case filed", "complaint filed", "indictment filed"), killer=True),
    AlertRule("case_reactivated", "Case reactivated or reopened", "case_flow", "pro", "medium", ("reactivated", "reopened", "restored to active")),
    AlertRule("case_transferred", "Case transferred", "case_flow", "pro", "medium", ("transferred", "bindover", "certified to")),
    AlertRule("case_dismissed", "Case dismissed", "case_flow", "pro", "high", ("dismissed",), killer=True),
    AlertRule("final_disposition", "Final disposition entered", "case_flow", "pro", "high", ("plea", "found guilty", "not guilty", "convicted", "acquitted", "sentenced")),
    AlertRule("hearing_scheduled", "New hearing scheduled", "schedule", "basic", "medium", ("hearing set", "scheduled", "arraignment", "pretrial"), killer=True),
    AlertRule("hearing_rescheduled", "Hearing rescheduled or continued", "schedule", "basic", "medium", ("continued", "rescheduled", "reset"), killer=True),
    AlertRule("hearing_canceled", "Hearing canceled or not held", "schedule", "pro", "medium", ("not held", "canceled", "vacated")),
    AlertRule("trial_set", "Trial date set", "schedule", "pro", "high", ("trial set", "jury trial set", "bench trial set")),
    AlertRule("capias_issued", "Capias issued", "custody", "pro", "critical", ("capias issued",), killer=True),
    AlertRule("capias_recalled", "Capias recalled", "custody", "pro", "high", ("capias recalled", "capias withdrawn")),
    AlertRule("arrest_recorded", "Arrest recorded", "custody", "pro", "high", ("arrested", "booked")),
    AlertRule("bond_changed", "Bond set or modified", "custody", "pro", "high", ("bond", "recognizance", "surety")),
    AlertRule("fta", "Failure to appear", "custody", "pro", "critical", ("failure to appear", "fta"), killer=True),
    AlertRule("new_charge", "New charge added", "charges", "pro", "high", ("indict", "count"), killer=True),
    AlertRule("charge_amended", "Charge amended", "charges", "pro", "critical", ("amended", "amendment"), killer=True),
    AlertRule("charge_dismissed", "Charge dismissed", "charges", "pro", "high", ("count dismissed", "charge dismissed")),
    AlertRule("enhancement_added", "Enhancement added", "charges", "premium", "critical", ("firearm specification", "repeat violent offender", "specification")),
    AlertRule("counts_merged", "Counts merged or separated", "charges", "premium", "high", ("merged for sentencing", "counts merged", "count severed")),
    AlertRule("motion_filed", "Motion filed", "filings", "pro", "medium", ("motion filed",)),
    AlertRule("motion_ruled", "Motion ruled on", "filings", "pro", "high", ("motion granted", "motion denied", "ruled")),
    AlertRule("discovery_request", "Discovery request filed", "filings", "pro", "medium", ("discovery request", "demand for discovery")),
    AlertRule("discovery_response", "Discovery response filed", "filings", "pro", "medium", ("discovery response", "response to discovery")),
    AlertRule("suppression_motion", "Suppression motion filed", "filings", "pro", "critical", ("motion to suppress",), killer=True),
    AlertRule("violation_filed", "Violation filed", "probation", "pro", "critical", ("violation filed", "community control violation"), killer=True),
    AlertRule("violation_hearing", "Violation hearing scheduled", "probation", "pro", "high", ("violation hearing", "pv hearing")),
    AlertRule("sanctions_modified", "Sanctions modified", "probation", "pro", "high", ("sanctions modified", "conditions modified")),
    AlertRule("fines_assessed", "Fines assessed", "financial", "basic", "low", ("fine", "costs taxed")),
    AlertRule("payment_posted", "Payment posted", "financial", "basic", "low", ("payment posted", "receipt")),
    AlertRule("restitution_ordered", "Restitution ordered", "financial", "pro", "medium", ("restitution",)),
    AlertRule("als_notice", "ALS notice referenced", "ovi", "pro", "high", ("als", "administrative license suspension")),
    AlertRule("license_suspension", "License suspension entry", "ovi", "pro", "high", ("license suspension", "suspension imposed")),
    AlertRule("driving_privileges", "Driving privileges granted or modified", "ovi", "pro", "high", ("driving privileges", "occupational privileges")),
    AlertRule("interlock_ordered", "Interlock ordered", "ovi", "pro", "high", ("interlock", "ignition interlock")),
    AlertRule("attorney_added", "Attorney added", "representation", "basic", "critical", ("attorney", "appearance"), killer=True),
    AlertRule("attorney_withdrawn", "Attorney withdrawn", "representation", "basic", "critical", ("withdraw", "counsel"), killer=True),
    AlertRule("public_defender_assigned", "Public defender assigned", "representation", "basic", "high", ("public defender", "appointed counsel")),
    AlertRule("private_counsel_substituted", "Private counsel substituted", "representation", "pro", "high", ("substitute counsel", "retained counsel")),
)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _has_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token in text for token in tokens)


def _has_all(text: str, tokens: Iterable[str]) -> bool:
    return all(token in text for token in tokens)


def _entry_identity(entry: dict) -> str:
    key = entry.get("entry_id") or ""
    date = entry.get("date") or ""
    return f"{key}|{date}|{_normalize(entry.get('text') or '')}"


def _detect_anomalies(previous_entries: list[dict], current_entries: list[dict]) -> list[AlertEvent]:
    events: list[AlertEvent] = []

    # Duplicate/conflicting entries
    normalized_to_count: dict[str, int] = {}
    for e in current_entries:
        t = _normalize(e.get("text") or "")
        normalized_to_count[t] = normalized_to_count.get(t, 0) + 1
    duplicates = [t for t, count in normalized_to_count.items() if t and count > 1]
    if duplicates:
        events.append(
            AlertEvent(
                code="duplicate_conflicting_entries",
                title="Duplicate or conflicting entries detected",
                category="integrity",
                tier="premium",
                severity="high",
                detail="Multiple identical docket lines were detected in the current snapshot.",
                matched_entries=duplicates[:5],
            )
        )

    # Modified/replaced entries: same id/date but changed text
    prev_by_anchor: dict[str, str] = {}
    for e in previous_entries:
        anchor = f"{e.get('entry_id') or ''}|{e.get('date') or ''}"
        prev_by_anchor[anchor] = _normalize(e.get("text") or "")

    replaced: list[str] = []
    for e in current_entries:
        anchor = f"{e.get('entry_id') or ''}|{e.get('date') or ''}"
        if anchor in prev_by_anchor and prev_by_anchor[anchor] and prev_by_anchor[anchor] != _normalize(e.get("text") or ""):
            replaced.append(e.get("text") or "")

    if replaced:
        events.append(
            AlertEvent(
                code="entry_modified_replaced",
                title="Entry modified or replaced",
                category="integrity",
                tier="premium",
                severity="critical",
                detail="At least one docket anchor remained the same while text changed between snapshots.",
                matched_entries=replaced[:5],
            )
        )

    # Missing expected entry: previous line vanished entirely
    prev_ids = {_entry_identity(e) for e in previous_entries}
    cur_ids = {_entry_identity(e) for e in current_entries}
    missing = sorted(prev_ids - cur_ids)
    if missing:
        events.append(
            AlertEvent(
                code="missing_expected_entry",
                title="Missing expected entry (gap)",
                category="integrity",
                tier="premium",
                severity="critical",
                detail="At least one previously observed docket line is missing in the current snapshot.",
                matched_entries=missing[:5],
            )
        )

    # Backdated timestamp heuristic
    backdated = []
    for e in current_entries:
        filed_at = (e.get("filed_at") or "")
        date = (e.get("date") or "")
        if filed_at and date and filed_at < date:
            backdated.append(e.get("text") or "")
    if backdated:
        events.append(
            AlertEvent(
                code="backdated_timestamp",
                title="Entry appears backdated",
                category="integrity",
                tier="premium",
                severity="high",
                detail="Filed timestamp appears earlier than docket date for one or more entries.",
                matched_entries=backdated[:5],
            )
        )

    return events


def scan_alerts(payload: AlertScanRequest) -> AlertScanResponse:
    prev = [e.model_dump() for e in payload.previous_entries]
    cur = [e.model_dump() for e in payload.current_entries]

    prev_index = {_entry_identity(e) for e in prev}
    added_entries = [e for e in cur if _entry_identity(e) not in prev_index]

    events: list[AlertEvent] = []

    # Rule-based detections on new entries only
    for entry in added_entries:
        text = _normalize(entry.get("text") or "")
        for rule in RULES:
            if _has_any(text, rule.keywords_any) and _has_all(text, rule.keywords_all):
                events.append(
                    AlertEvent(
                        code=rule.code,
                        title=rule.title,
                        category=rule.category,
                        tier=rule.tier,
                        severity=rule.severity,
                        detail=f"Detected from new docket text: {entry.get('text', '')[:220]}",
                        matched_entries=[entry.get("text") or ""],
                    )
                )

    events.extend(_detect_anomalies(prev, cur))

    # Dedupe by code + detail prefix
    deduped: list[AlertEvent] = []
    seen: set[str] = set()
    for event in events:
        key = f"{event.code}|{event.matched_entries[0] if event.matched_entries else ''}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)

    killer_codes = {r.code for r in RULES if r.killer}
    killer_events = [e for e in deduped if e.code in killer_codes or e.severity == "critical"]

    totals = {
        "all": len(deduped),
        "basic": sum(1 for e in deduped if e.tier == "basic"),
        "pro": sum(1 for e in deduped if e.tier == "pro"),
        "premium": sum(1 for e in deduped if e.tier == "premium"),
        "critical": sum(1 for e in deduped if e.severity == "critical"),
        "killer": len(killer_events),
    }

    guidance = [
        "Position alerts as docket intelligence and risk awareness, not lead targeting.",
        "Escalate critical events to immediate notification channels.",
        "Bundle pattern/anomaly alerts in premium tiers for differentiation.",
    ]

    return AlertScanResponse(
        case_number=payload.case_number,
        court=payload.court,
        totals=totals,
        events=deduped,
        killer_events=killer_events,
        guidance=guidance,
    )
