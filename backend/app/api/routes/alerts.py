from fastapi import APIRouter

from app.schemas.alerts import AlertScanRequest, AlertScanResponse
from app.services.alert_engine import scan_alerts

router = APIRouter(tags=["alerts"])


@router.post("/alerts/scan", response_model=AlertScanResponse)
def post_alert_scan(payload: AlertScanRequest) -> AlertScanResponse:
    return scan_alerts(payload)
