from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class CaseRow(BaseModel):
    case_number: str
    year: int
    status: str
    defendant_name: Optional[str] = None
    judge_name: Optional[str] = None
    charges: List[str] = []
    filed_date: Optional[str] = None  # ISO date string
    has_defense_attorney: bool = False
    defense_attorneys: List[str] = []


class CaseIntelligenceResponse(BaseModel):
    attorney_name: Optional[str] = None
    my_cases: List[CaseRow] = []
    unassigned_filings: List[CaseRow] = []
    my_cases_count: int = 0
    unassigned_count: int = 0
