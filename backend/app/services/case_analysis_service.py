from __future__ import annotations

from app.schemas.case_analysis import (
    CaseAnalysisRequest,
    CaseAnalysisResponse,
    CaseSummary,
    CTAOutput,
    RiskFlag,
)
from app.services.question_engine import generate_questions


def analyze_case(payload: CaseAnalysisRequest) -> CaseAnalysisResponse:
    charge_codes = [charge.code for charge in payload.charges]
    joined = " ".join(charge_codes)
    facts = payload.facts.model_dump()

    content_routes = ["/what-happens-after-dui-arrest-ohio"]
    risk_flags: list[RiskFlag] = []

    primary_case_type = "general-traffic"
    confidence = 0.65
    urgency = "medium"
    timeline_stage = "intake"
    recommended_alerts = [
        "new_case_filed",
        "hearing_scheduled",
        "attorney_added",
    ]
    alert_tier_recommendation = "basic"

    if "4511.19" in joined:
        primary_case_type = "OVI-first-offense" if payload.facts.prior_ovi_within_10y == 0 else "OVI-repeat-risk"
        confidence = 0.92
        urgency = "high"
        timeline_stage = "post-arrest-pre-first-appearance"
        content_routes.extend(
            [
                "/ovi-lawyer-cleveland",
                "/will-i-lose-my-license-ohio-dui",
                "/first-offense-dui-ohio-penalties",
                "/als-suspension-ohio",
            ]
        )
        risk_flags.append(
            RiskFlag(
                type="license",
                severity="high",
                title="Immediate suspension risk",
                detail="An immediate suspension issue may need review right away after an OVI arrest.",
            )
        )
        recommended_alerts.extend(
            [
                "charge_amended",
                "case_dismissed",
                "capias_issued",
                "als_notice",
                "license_suspension",
                "driving_privileges",
            ]
        )
        alert_tier_recommendation = "pro"
        risk_flags.append(
            RiskFlag(
                type="procedure",
                severity="medium",
                title="Fast early timeline",
                detail="OVI cases move quickly in the first days, so paperwork collection matters.",
            )
        )

    if facts.get("chemical_test") == "refused":
        content_routes.extend([
            "/should-i-refuse-breath-test-ohio",
            "/refusal-vs-failed-test-ohio-ovi",
        ])
        risk_flags.append(
            RiskFlag(
                type="license",
                severity="high",
                title="Refusal-based suspension exposure",
                detail="A refusal can change the license side of the case immediately.",
            )
        )
        recommended_alerts.append("suppression_motion")
        alert_tier_recommendation = "premium"

    if facts.get("cdl"):
        risk_flags.append(
            RiskFlag(
                type="employment",
                severity="high",
                title="Commercial driving risk",
                detail="Commercial drivers can face extra exposure from any suspension or loss of privileges.",
            )
        )
        recommended_alerts.append("bond_changed")

    questions = generate_questions(charge_codes, facts)

    return CaseAnalysisResponse(
        summary=CaseSummary(
            primary_case_type=primary_case_type,
            confidence=confidence,
            urgency=urgency,
            timeline_stage=timeline_stage,
        ),
        risk_flags=risk_flags,
        likely_questions=questions,
        content_routes=list(dict.fromkeys(content_routes)),
        recommended_alerts=list(dict.fromkeys(recommended_alerts)),
        alert_tier_recommendation=alert_tier_recommendation,
        cta=CTAOutput(
            type="call",
            label="Talk to Aaron Brockler now",
            target="/brocklerlaw",
        ),
        disclaimer="General information only. Not legal advice.",
    )
