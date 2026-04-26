from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user
from app.schemas.case_intelligence import CaseIntelligenceResponse
from app.services.case_intelligence_service import get_case_intelligence
from database.session import SessionLocal

router = APIRouter(tags=["cases"], dependencies=[Depends(get_current_user)])


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/cases/intelligence", response_model=CaseIntelligenceResponse)
def case_intelligence(
    attorney_name: Optional[str] = None,
    days_back: int = 30,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> CaseIntelligenceResponse:
    """
    Return the calling attorney's active cases + unassigned recent filings.

    - **attorney_name**: partial name match (case-insensitive) against the attorneys table
    - **days_back**: how many days back to scan for new unassigned filings (default 30)
    - **limit**: max rows per bucket
    """
    return get_case_intelligence(db, attorney_name=attorney_name, days_back=days_back, limit=limit)
