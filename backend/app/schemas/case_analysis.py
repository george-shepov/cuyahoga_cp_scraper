from typing import List, Optional
from pydantic import BaseModel, Field


class ChargeInput(BaseModel):
    code: str
    label: str


class FactsInput(BaseModel):
    chemical_test: str = "unknown"
    prior_ovi_within_10y: int = 0
    cdl: bool = False
    arrest_date: Optional[str] = None
    incident_date: Optional[str] = None


class CaseAnalysisRequest(BaseModel):
    case_number: Optional[str] = None
    court: Optional[str] = None
    defendant_name: Optional[str] = None
    charges: List[ChargeInput] = Field(default_factory=list)
    facts: FactsInput = Field(default_factory=FactsInput)


class RiskFlag(BaseModel):
    type: str
    severity: str
    title: str
    detail: str


class CaseSummary(BaseModel):
    primary_case_type: str
    confidence: float
    urgency: str
    timeline_stage: str


class CTAOutput(BaseModel):
    type: str
    label: str
    target: str


class CaseAnalysisResponse(BaseModel):
    summary: CaseSummary
    risk_flags: List[RiskFlag]
    likely_questions: List[str]
    content_routes: List[str]
    recommended_alerts: List[str] = Field(default_factory=list)
    alert_tier_recommendation: str = "basic"
    cta: CTAOutput
    disclaimer: str
