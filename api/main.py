"""
FastAPI Application for Cuyahoga Court Analytics
Provides REST API for attorney recommendations, analytics, and document analysis
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from database.models_postgres import ContentStatus, ContentType
from database.session import SessionLocal, init_db

# Import services
from services.attorney_recommender import AttorneyRecommender
from services.analytics_calculator import AnalyticsCalculator
from services.document_analyzer import DocumentAnalyzer
from services.knowledge_base import KnowledgeBaseService
from services.quadrant_analyzer import QuadrantAnalyzer

app = FastAPI(
    title="Cuyahoga Court Analytics API",
    description="Attorney recommendations, performance analytics, and case insights",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class AttorneyRecommendationRequest(BaseModel):
    judge_id: int
    prosecutor_id: int
    charge_type: str = "GENERAL"
    top_n: int = 5


class AttorneyRecommendationResponse(BaseModel):
    attorney_id: int
    attorney_name: str
    firm: Optional[str]
    score: float
    overall_win_rate: float
    matchup_win_rate: float
    charge_type_win_rate: float
    total_cases: int
    effectiveness_score: float
    coverage_label: str
    key_factors: List[str] = Field(default_factory=list)
    explanation_preview: Optional[str] = None
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)


class MatchupAnalysisResponse(BaseModel):
    judge: Dict[str, Any]
    prosecutor: Dict[str, Any]
    matchup: Dict[str, Any]
    recommendation: Dict[str, Any]


class JudgePerformanceResponse(BaseModel):
    judge_id: int
    total_cases: int
    conviction_rate: float
    defendant_favorability_score: float
    avg_days_to_disposition: float


class KnowledgeContentResponse(BaseModel):
    slug: str
    title: str
    question: Optional[str]
    summary: Optional[str]
    body: str
    content_type: str
    status: str
    charge_type: Optional[str]
    tags: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    reviewer_name: Optional[str]
    reviewed_at: Optional[datetime]
    approved_at: Optional[datetime]
    updated_at: datetime


class ContentDraftRequest(BaseModel):
    title: str
    body: str
    content_type: ContentType
    question: Optional[str] = None
    summary: Optional[str] = None
    charge_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    source_payload: Dict[str, Any] = Field(default_factory=dict)
    source_metrics: Dict[str, Any] = Field(default_factory=dict)


class ContentGenerationRequest(BaseModel):
    question: str
    content_type: ContentType = ContentType.FAQ
    title: Optional[str] = None
    charge_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    source_context: Dict[str, Any] = Field(default_factory=dict)
    source_metrics: Dict[str, Any] = Field(default_factory=dict)


class ContentReviewActionRequest(BaseModel):
    action: str = Field(..., description="One of: submit, under_review, approve, archive")
    reviewer_name: str


class ContentExportResponse(BaseModel):
    generated_at: datetime
    total_items: int
    items: List[Dict[str, Any]] = Field(default_factory=list)


class RecommendationExplanationRequest(BaseModel):
    judge_id: int
    prosecutor_id: int
    attorney_id: int
    charge_type: str = "GENERAL"


class RecommendationExplanationResponse(BaseModel):
    attorney_id: int
    attorney_name: str
    summary: str
    key_factors: List[str] = Field(default_factory=list)
    coverage_label: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


# Dependency for database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
async def startup_event():
    init_db()


def serialize_content(content) -> KnowledgeContentResponse:
    return KnowledgeContentResponse(
        slug=content.slug,
        title=content.title,
        question=content.question,
        summary=content.summary,
        body=content.body,
        content_type=content.content_type.value,
        status=content.status.value,
        charge_type=content.charge_type,
        tags=content.tags or [],
        citations=content.citations or [],
        reviewer_name=content.reviewer_name,
        reviewed_at=content.reviewed_at,
        approved_at=content.approved_at,
        updated_at=content.updated_at,
    )


# API Endpoints

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Cuyahoga Court Analytics API",
        "version": "1.0.0",
        "endpoints": {
            "attorney_recommendations": "/api/v1/recommendations",
            "matchup_analysis": "/api/v1/matchup",
            "judge_performance": "/api/v1/judges/{judge_id}/performance",
            "prosecutor_performance": "/api/v1/prosecutors/{prosecutor_id}/performance",
            "attorney_performance": "/api/v1/attorneys/{attorney_id}/performance",
            "document_analysis": "/api/v1/documents/analyze",
            "case_quadrant": "/api/v1/cases/{case_id}/quadrant",
            "content": "/api/v1/content",
            "generate_content_draft": "/api/v1/content/drafts/generate",
            "review_content": "/api/v1/content/{slug}/review",
            "content_export": "/api/v1/content/export",
            "recommendation_explanation": "/api/v1/recommendations/explain",
        }
    }


@app.post("/api/v1/recommendations", response_model=List[AttorneyRecommendationResponse])
async def get_attorney_recommendations(
    request: AttorneyRecommendationRequest,
    db: Session = Depends(get_db)
):
    """
    Get attorney recommendations for a specific judge-prosecutor matchup
    
    Returns top N attorneys ranked by predicted success rate
    """
    try:
        recommender = AttorneyRecommender(db)
        recommendations = recommender.get_recommendations(
            judge_id=request.judge_id,
            prosecutor_id=request.prosecutor_id,
            charge_type=request.charge_type,
            top_n=request.top_n
        )
        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/recommendations/explain", response_model=RecommendationExplanationResponse)
async def explain_attorney_recommendation(
    request: RecommendationExplanationRequest,
    db: Session = Depends(get_db)
):
    """Return a structured explanation for one attorney recommendation."""
    try:
        recommender = AttorneyRecommender(db)
        explanation = recommender.explain_recommendation(
            judge_id=request.judge_id,
            prosecutor_id=request.prosecutor_id,
            charge_type=request.charge_type,
            attorney_id=request.attorney_id,
        )
        if explanation.get("error"):
            raise HTTPException(status_code=404, detail=explanation["error"])

        kb_service = KnowledgeBaseService(db)
        normalized = kb_service.build_recommendation_explanation(
            judge_id=request.judge_id,
            prosecutor_id=request.prosecutor_id,
            charge_type=request.charge_type,
            recommendation={
                "attorney_id": explanation["attorney_id"],
                "attorney_name": explanation["attorney_name"],
                "explanation_preview": explanation["summary"],
                "key_factors": explanation["key_factors"],
                "coverage_label": explanation["coverage_label"],
                "score_breakdown": explanation["evidence"].get("score_breakdown", {}),
                "overall_win_rate": explanation["evidence"].get("overall_win_rate"),
                "matchup_win_rate": explanation["evidence"].get("matchup_win_rate"),
                "charge_type_win_rate": explanation["evidence"].get("charge_type_win_rate"),
                "total_cases": explanation["evidence"].get("total_cases"),
                "effectiveness_score": None,
            },
        )

        kb_service.save_recommendation_explanation(
            judge_id=request.judge_id,
            prosecutor_id=request.prosecutor_id,
            attorney_id=request.attorney_id,
            charge_type=request.charge_type,
            explanation_payload=normalized,
        )

        return RecommendationExplanationResponse(
            attorney_id=explanation["attorney_id"],
            attorney_name=explanation["attorney_name"],
            summary=normalized["summary"],
            key_factors=normalized["key_factors"],
            coverage_label=normalized["coverage_label"],
            evidence=normalized["evidence"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/content", response_model=List[KnowledgeContentResponse])
async def list_knowledge_content(
    content_type: Optional[ContentType] = Query(None, description="Content type filter"),
    charge_type: Optional[str] = Query(None, description="Charge type filter"),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List approved knowledge-base content."""
    try:
        service = KnowledgeBaseService(db)
        items = service.list_content(
            status=ContentStatus.APPROVED,
            content_type=content_type,
            charge_type=charge_type,
            limit=limit,
        )
        return [serialize_content(item) for item in items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/content/export", response_model=ContentExportResponse)
async def export_approved_content(
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db)
):
    """Export approved content as a lightweight JSON feed for external publishing."""
    try:
        service = KnowledgeBaseService(db)
        items = service.export_approved_content(limit=limit)
        return ContentExportResponse(
            generated_at=datetime.utcnow(),
            total_items=len(items),
            items=items,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/content/{slug}", response_model=KnowledgeContentResponse)
async def get_knowledge_content(
    slug: str,
    db: Session = Depends(get_db)
):
    """Fetch one approved knowledge-base entry by slug."""
    try:
        service = KnowledgeBaseService(db)
        item = service.get_content_by_slug(slug, status=ContentStatus.APPROVED)
        if item is None:
            raise HTTPException(status_code=404, detail="Content not found")
        return serialize_content(item)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/content/drafts", response_model=KnowledgeContentResponse)
async def create_content_draft(
    request: ContentDraftRequest,
    db: Session = Depends(get_db)
):
    """Create a draft content record that requires review before approval."""
    try:
        service = KnowledgeBaseService(db)
        item = service.create_draft(
            title=request.title,
            body=request.body,
            content_type=request.content_type,
            question=request.question,
            summary=request.summary,
            charge_type=request.charge_type,
            tags=request.tags,
            citations=request.citations,
            source_payload=request.source_payload,
            source_metrics=request.source_metrics,
        )
        return serialize_content(item)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/content/drafts/generate", response_model=KnowledgeContentResponse)
async def generate_content_draft(
    request: ContentGenerationRequest,
    db: Session = Depends(get_db)
):
    """Generate a review-required draft answer from a question and source context."""
    try:
        service = KnowledgeBaseService(db)
        item = await service.generate_draft_answer(
            question=request.question,
            title=request.title,
            content_type=request.content_type,
            source_context=request.source_context,
            source_metrics=request.source_metrics,
            citations=request.citations,
            charge_type=request.charge_type,
            tags=request.tags,
        )
        return serialize_content(item)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/content/{slug}/review", response_model=KnowledgeContentResponse)
async def review_content_action(
    slug: str,
    request: ContentReviewActionRequest,
    db: Session = Depends(get_db)
):
    """Transition a content item through review states without direct DB edits."""
    try:
        service = KnowledgeBaseService(db)
        updated = service.review_action(
            slug=slug,
            action=request.action,
            reviewer_name=request.reviewer_name,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Content not found")
        return serialize_content(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/matchup", response_model=MatchupAnalysisResponse)
async def get_matchup_analysis(
    judge_id: int = Query(..., description="Judge ID"),
    prosecutor_id: int = Query(..., description="Prosecutor ID"),
    db: Session = Depends(get_db)
):
    """
    Get detailed analysis of a judge-prosecutor matchup
    
    Includes historical performance, difficulty level, and strategy suggestions
    """
    try:
        recommender = AttorneyRecommender(db)
        analysis = recommender.get_matchup_analysis(judge_id, prosecutor_id)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/judges/{judge_id}/performance", response_model=JudgePerformanceResponse)
async def get_judge_performance(
    judge_id: int,
    db: Session = Depends(get_db)
):
    """Get comprehensive performance metrics for a judge"""
    try:
        calculator = AnalyticsCalculator(db)
        performance = calculator.calculate_judge_performance(judge_id)
        return performance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/prosecutors/{prosecutor_id}/performance")
async def get_prosecutor_performance(
    prosecutor_id: int,
    db: Session = Depends(get_db)
):
    """Get comprehensive performance metrics for a prosecutor"""
    try:
        calculator = AnalyticsCalculator(db)
        performance = calculator.calculate_prosecutor_performance(prosecutor_id)
        return performance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/attorneys/{attorney_id}/performance")
async def get_attorney_performance(
    attorney_id: int,
    db: Session = Depends(get_db)
):
    """Get comprehensive performance metrics for a defense attorney"""
    try:
        calculator = AnalyticsCalculator(db)
        performance = calculator.calculate_defense_attorney_performance(attorney_id)
        return performance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/documents/analyze")
async def analyze_document(
    pdf_path: str = Query(..., description="Path to PDF file")
):
    """Analyze a court document PDF using LLM"""
    try:
        analyzer = DocumentAnalyzer()
        analysis = await analyzer.analyze_pdf(pdf_path)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/cases/{case_id}/quadrant")
async def get_case_quadrant_analysis(
    case_id: int,
    db: Session = Depends(get_db)
):
    """Get quadrant analysis for a specific case"""
    try:
        from database.models_postgres import Case

        # Get case data
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Convert to dict format expected by quadrant analyzer
        case_data = {
            "summary": {
                "charges": [{"description": c.description} for c in case.charges] if case.charges else []
            },
            "co_defendants": [],
            "docket": [],
            "attorneys": [],
            "costs": [],
            "outcome": {
                "final_status": case.outcome.final_status if case.outcome else "PENDING",
                "sentence_duration_days": case.outcome.sentence_duration_days if case.outcome else 0,
                "fine_amount": case.outcome.fine_amount if case.outcome else 0,
                "restitution_amount": case.outcome.restitution_amount if case.outcome else 0,
            }
        }

        analyzer = QuadrantAnalyzer()
        quadrant_analysis = analyzer.analyze_case(case_data)

        return quadrant_analysis
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/attorneys/compare")
async def compare_attorneys(
    attorney_ids: List[int],
    judge_id: int = Query(..., description="Judge ID"),
    prosecutor_id: int = Query(..., description="Prosecutor ID"),
    charge_type: str = Query("GENERAL", description="Charge type"),
    db: Session = Depends(get_db)
):
    """Compare multiple attorneys side-by-side for a specific matchup"""
    try:
        recommender = AttorneyRecommender(db)
        comparison = recommender.compare_attorneys(
            attorney_ids=attorney_ids,
            judge_id=judge_id,
            prosecutor_id=prosecutor_id,
            charge_type=charge_type
        )
        return comparison
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/statistics/yearly-trends")
async def get_yearly_trends(
    entity_type: str = Query(..., description="JUDGE, PROSECUTOR, or DEFENSE_ATTORNEY"),
    entity_id: int = Query(..., description="Entity ID"),
    start_year: Optional[int] = Query(None, description="Start year"),
    end_year: Optional[int] = Query(None, description="End year"),
    db: Session = Depends(get_db)
):
    """Get yearly trend data for a judge, prosecutor, or attorney"""
    try:
        from database.analytics_models import YearlyTrends

        query = db.query(YearlyTrends).filter(
            YearlyTrends.entity_type == entity_type,
            YearlyTrends.entity_id == entity_id
        )

        if start_year:
            query = query.filter(YearlyTrends.year >= start_year)
        if end_year:
            query = query.filter(YearlyTrends.year <= end_year)

        trends = query.order_by(YearlyTrends.year).all()

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "trends": [
                {
                    "year": t.year,
                    "total_cases": t.total_cases,
                    "new_cases": t.new_cases,
                    "closed_cases": t.closed_cases,
                    "conviction_rate": t.conviction_rate,
                    "win_rate": t.win_rate,
                    "avg_case_lifetime_days": t.avg_case_lifetime_days,
                }
                for t in trends
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

