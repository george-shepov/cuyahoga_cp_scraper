from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from database.models_postgres import UsageLedger


def record_usage(
    db: Session,
    *,
    account_id: str,
    meter_key: str,
    value: int,
    source: str = "app",
    case_number: str | None = None,
) -> UsageLedger:
    entry = UsageLedger(
        account_id=account_id,
        meter_key=meter_key,
        value=value,
        source=source,
        case_number=case_number,
        event_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
