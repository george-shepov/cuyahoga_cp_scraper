from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class DocketEntryInput(BaseModel):
    entry_id: Optional[str] = None
    date: Optional[str] = None
    filed_at: Optional[str] = None
    text: str


class AlertScanRequest(BaseModel):
    case_number: Optional[str] = None
    court: Optional[str] = None
    previous_entries: List[DocketEntryInput] = Field(default_factory=list)
    current_entries: List[DocketEntryInput] = Field(default_factory=list)


class AlertEvent(BaseModel):
    code: str
    title: str
    category: str
    tier: str
    severity: str
    detail: str
    matched_entries: List[str] = Field(default_factory=list)


class AlertScanResponse(BaseModel):
    case_number: Optional[str] = None
    court: Optional[str] = None
    totals: dict[str, int]
    events: List[AlertEvent]
    killer_events: List[AlertEvent]
    guidance: List[str]
