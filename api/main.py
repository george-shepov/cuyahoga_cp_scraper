"""
FastAPI Application for Cuyahoga Court Analytics
Provides REST API for attorney recommendations, analytics, and document analysis
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

# Import services
from services.attorney_recommender import AttorneyRecommender
from services.analytics_calculator import AnalyticsCalculator
from services.document_analyzer import DocumentAnalyzer
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


# Dependency for database session
def get_db():
    # TODO: Implement actual database session
    # from database.postgres_client import SessionLocal
    # db = SessionLocal()
    # try:
    #     yield db
    # finally:
    #     db.close()
    pass


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
            "co_defendants": [],  # TODO: populate from database
            "docket": [],  # TODO: populate from database
            "attorneys": [],  # TODO: populate from database
            "costs": [],  # TODO: populate from database
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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

