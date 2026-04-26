from __future__ import annotations

from datetime import datetime, timezone

from app.services.billing_service import get_billing_summary
from database.models_postgres import BillingAccount, UsageLedger
from database.session import SessionLocal, init_db


def test_billing_summary_aggregates_usage() -> None:
    init_db()
    db = SessionLocal()
    try:
        account_id = "test-account-summary"

        existing = db.query(BillingAccount).filter(BillingAccount.account_id == account_id).one_or_none()
        if existing is None:
            db.add(BillingAccount(account_id=account_id, plan_code="pro"))
            db.commit()

        db.add(
            UsageLedger(
                account_id=account_id,
                meter_key="alerts_sent",
                value=120,
                source="test",
                event_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            UsageLedger(
                account_id=account_id,
                meter_key="monitored_cases",
                value=10,
                source="test",
                event_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        summary = get_billing_summary(db, account_id=account_id)

        assert summary.account_id == account_id
        assert summary.plan_code == "pro"
        assert any(m.meter_key == "alerts_sent" and m.used >= 120 for m in summary.meters)
        assert any(m.meter_key == "monitored_cases" and m.used >= 10 for m in summary.meters)
    finally:
        db.close()
