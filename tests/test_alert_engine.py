from app.schemas.alerts import AlertScanRequest, DocketEntryInput
from app.services.alert_engine import scan_alerts


def test_alert_engine_detects_killer_events_and_totals() -> None:
    payload = AlertScanRequest(
        case_number="CR-26-000001-A",
        court="Cuyahoga CP",
        previous_entries=[
            DocketEntryInput(entry_id="1", date="2026-04-20", text="ARRAIGNMENT HELD"),
        ],
        current_entries=[
            DocketEntryInput(entry_id="1", date="2026-04-20", text="ARRAIGNMENT HELD"),
            DocketEntryInput(entry_id="2", date="2026-04-21", text="MOTION TO SUPPRESS FILED"),
            DocketEntryInput(entry_id="3", date="2026-04-21", text="ATTORNEY APPEARANCE FILED"),
            DocketEntryInput(entry_id="4", date="2026-04-21", text="CAPIAS ISSUED"),
        ],
    )

    result = scan_alerts(payload)

    codes = {event.code for event in result.events}
    assert "suppression_motion" in codes
    assert "attorney_added" in codes
    assert "capias_issued" in codes
    assert result.totals["killer"] >= 1
    assert result.totals["all"] >= 3


def test_alert_engine_detects_missing_entry_gap() -> None:
    payload = AlertScanRequest(
        previous_entries=[
            DocketEntryInput(entry_id="1", date="2026-04-20", text="ARRAIGNMENT HELD"),
            DocketEntryInput(entry_id="2", date="2026-04-20", text="BOND SET"),
        ],
        current_entries=[
            DocketEntryInput(entry_id="1", date="2026-04-20", text="ARRAIGNMENT HELD"),
        ],
    )

    result = scan_alerts(payload)
    assert any(event.code == "missing_expected_entry" for event in result.events)
