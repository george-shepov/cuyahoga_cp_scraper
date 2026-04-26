from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, not_, exists, and_
from sqlalchemy.orm import Session, joinedload

from app.schemas.case_intelligence import CaseIntelligenceResponse, CaseRow
from database.models_postgres import Case, CaseAttorney, Attorney, Defendant, Judge, Charge


def _case_to_row(case: Case, defense_attorneys: list[str], candidate_case_ids: list[str] | None = None) -> CaseRow:
    case_date = case.indictment_date or case.arrest_date
    return CaseRow(
        case_number=case.case_id or case.case_number,
        year=case.year,
        status=case.status.value if case.status else "UNKNOWN",
        defendant_name=case.defendant.name if case.defendant else "Unknown Defendant",
        judge_name=case.judge.name if case.judge else None,
        charges=[c.description for c in (case.charges or [])[:3]],
        case_date=case_date.isoformat() if case_date else None,
        filed_date=case.indictment_date.isoformat() if case.indictment_date else (
            case.arrest_date.isoformat() if case.arrest_date else None
        ),
        last_changed_at=case.updated_at.isoformat() if case.updated_at else None,
        last_updated_at=case.scraped_at.isoformat() if case.scraped_at else None,
        has_defense_attorney=len(defense_attorneys) > 0,
        defense_attorneys=defense_attorneys,
        candidate_case_ids=candidate_case_ids or [],
    )


def _candidate_case_ids(db: Session, case: Case) -> list[str]:
    """Return full case IDs for the same year/number, including suffix variants (A/B/C/...)."""
    rows = (
        db.query(Case.case_id)
        .filter(
            Case.year == case.year,
            Case.number == case.number,
            Case.case_id.is_not(None),
        )
        .order_by(Case.case_id.asc())
        .all()
    )
    return [r[0] for r in rows if r and r[0]]


def get_case_intelligence(
    db: Session,
    attorney_name: Optional[str] = None,
    days_back: int = 30,
    limit: int = 100,
) -> CaseIntelligenceResponse:
    """
    Return:
     - my_cases: active cases where `attorney_name` is defense attorney of record
     - unassigned_filings: cases filed in last `days_back` days with no defense attorney
    """

    # ── My active cases ──────────────────────────────────────────────────────
    my_cases: list[CaseRow] = []
    if attorney_name and attorney_name.strip():
        q = (
            db.query(Case)
            .join(CaseAttorney, CaseAttorney.case_id == Case.id)
            .join(Attorney, Attorney.id == CaseAttorney.attorney_id)
            .options(
                joinedload(Case.defendant),
                joinedload(Case.judge),
                joinedload(Case.charges),
                joinedload(Case.case_attorneys).joinedload(CaseAttorney.attorney),
            )
            .filter(
                func.upper(Attorney.name).contains(attorney_name.upper()),
                func.upper(CaseAttorney.party).in_(["DEFENSE", "DEFENDANT"]),
            )
            .order_by(Case.updated_at.desc())
            .limit(limit)
        )
        for case in q.all():
            def_attys = [
                ca.attorney.name
                for ca in case.case_attorneys
                if ca.party and ca.party.upper() in ("DEFENSE", "DEFENDANT") and ca.attorney
            ]
            my_cases.append(_case_to_row(case, def_attys, _candidate_case_ids(db, case)))

    # ── Unassigned recent filings ─────────────────────────────────────────────
    cutoff = date.today() - timedelta(days=days_back)

    # Subquery: cases that DO have a defense attorney
    has_defense = (
        db.query(CaseAttorney.case_id)
        .filter(func.upper(CaseAttorney.party).in_(["DEFENSE", "DEFENDANT"]))
        .subquery()
    )

    unassigned_q = (
        db.query(Case)
        .options(
            joinedload(Case.defendant),
            joinedload(Case.judge),
            joinedload(Case.charges),
        )
        .filter(
            Case.id.not_in(has_defense),
            Case.scraped_at >= cutoff,
        )
        .order_by(Case.scraped_at.desc())
        .limit(limit)
    )

    unassigned: list[CaseRow] = []
    for case in unassigned_q.all():
        unassigned.append(_case_to_row(case, [], _candidate_case_ids(db, case)))

    return CaseIntelligenceResponse(
        attorney_name=attorney_name,
        my_cases=my_cases,
        unassigned_filings=unassigned,
        my_cases_count=len(my_cases),
        unassigned_count=len(unassigned),
    )
