from fastapi import APIRouter

from app.schemas.case_analysis import CaseAnalysisRequest, CaseAnalysisResponse
from app.services.case_analysis_service import analyze_case

router = APIRouter(tags=["case-analysis"])


@router.post("/case-analysis", response_model=CaseAnalysisResponse)
def post_case_analysis(payload: CaseAnalysisRequest) -> CaseAnalysisResponse:
    return analyze_case(payload)
