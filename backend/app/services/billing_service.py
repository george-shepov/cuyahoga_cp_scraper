from __future__ import annotations

from datetime import datetime, timezone
from calendar import monthrange

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.schemas.billing import BillingSummaryResponse, UsageMeterSummary
from database.models_postgres import BillingAccount, UsageLedger


PLAN_LIMITS: dict[str, dict[str, int]] = {
    "basic": {
        "alerts_sent": 1000,
        "monitored_cases": 100,
    },
    "pro": {
        "alerts_sent": 5000,
        "monitored_cases": 400,
    },
    "premium": {
        "alerts_sent": 25000,
        "monitored_cases": 1000,
    },
}


def _month_window(month: str | None) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if not month:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = monthrange(start.year, start.month)[1]
        end = start.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
        return start, end

    year, mm = month.split("-")
    start = datetime(int(year), int(mm), 1, tzinfo=timezone.utc)
    last_day = monthrange(start.year, start.month)[1]
    end = start.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
    return start, end


def _ensure_account(db: Session, account_id: str) -> BillingAccount:
    account = db.query(BillingAccount).filter(BillingAccount.account_id == account_id).one_or_none()
    if account:
        return account

    account = BillingAccount(account_id=account_id, plan_code="pro")
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_billing_summary(db: Session, account_id: str, month: str | None = None) -> BillingSummaryResponse:
    account = _ensure_account(db, account_id)
    plan_code = account.plan_code or "basic"
    limits = PLAN_LIMITS.get(plan_code, PLAN_LIMITS["basic"])
    period_start, period_end = _month_window(month)

    rows = (
        db.query(UsageLedger.meter_key, func.coalesce(func.sum(UsageLedger.value), 0))
        .filter(UsageLedger.account_id == account_id)
        .filter(UsageLedger.event_at >= period_start)
        .filter(UsageLedger.event_at <= period_end)
        .group_by(UsageLedger.meter_key)
        .all()
    )
    used_by_meter = {meter_key: int(total) for meter_key, total in rows}

    meters: list[UsageMeterSummary] = []
    projected_overage_units = 0
    for meter_key, included in limits.items():
        used = used_by_meter.get(meter_key, 0)
        overage = max(0, used - included)
        projected_overage_units += overage
        meters.append(
            UsageMeterSummary(
                meter_key=meter_key,
                included=included,
                used=used,
                overage=overage,
            )
        )

    return BillingSummaryResponse(
        account_id=account_id,
        plan_code=plan_code,
        stripe_customer_id=account.stripe_customer_id,
        period_start=period_start,
        period_end=period_end,
        meters=meters,
        projected_overage_units=projected_overage_units,
        notes=[
            "Usage is aggregated from usage_ledger events.",
            "Overage units are projected and can be wired to Stripe metered billing.",
        ],
    )
