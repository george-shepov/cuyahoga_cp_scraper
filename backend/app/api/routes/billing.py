from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.billing import BillingSummaryResponse, UsageRecordRequest
from app.services.billing_service import get_billing_summary
from app.services.usage_metering_service import record_usage
from database.session import SessionLocal

router = APIRouter(tags=["billing"])


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/billing/summary", response_model=BillingSummaryResponse)
def billing_summary(account_id: str = "demo-account", month: str | None = None, db: Session = Depends(get_db)) -> BillingSummaryResponse:
    return get_billing_summary(db, account_id=account_id, month=month)


@router.post("/billing/usage/record")
def billing_record_usage(payload: UsageRecordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    record_usage(
        db,
        account_id=payload.account_id,
        meter_key=payload.meter_key,
        value=payload.value,
        source=payload.source,
        case_number=payload.case_number,
    )
    return {"status": "ok"}
