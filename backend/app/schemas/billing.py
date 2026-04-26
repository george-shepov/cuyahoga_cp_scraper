from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class UsageRecordRequest(BaseModel):
    account_id: str
    meter_key: str
    value: int = Field(ge=0)
    source: str = "app"
    case_number: str | None = None


class UsageMeterSummary(BaseModel):
    meter_key: str
    included: int
    used: int
    overage: int


class BillingSummaryResponse(BaseModel):
    account_id: str
    plan_code: str
    stripe_customer_id: str | None = None
    period_start: datetime
    period_end: datetime
    meters: list[UsageMeterSummary]
    projected_overage_units: int = 0
    notes: list[str] = Field(default_factory=list)
