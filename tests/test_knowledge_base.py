import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from database.models_postgres import Base, ContentStatus, ContentType
from services.knowledge_base import KnowledgeBaseService


class FakeEmailService:
    def __init__(self):
        self.sent = []

    def send_email(self, *, to_email, subject, body):
        self.sent.append({"to": to_email, "subject": subject, "body": body})
        return {"status": "sent", "to": to_email}


def build_test_session():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return testing_session_local


def test_approved_content_only_exposed():
    testing_session_local = build_test_session()
    session = testing_session_local()
    try:
        service = KnowledgeBaseService(session)
        draft = service.create_draft(
            title="Draft answer",
            body="Pending review",
            content_type=ContentType.FAQ,
        )
        approved = service.create_draft(
            title="Approved answer",
            body="Reviewed copy",
            content_type=ContentType.FAQ,
        )
        service.approve_content(approved.slug, "Aaron Brockler")

        def override_get_db():
            db = testing_session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        response = client.get("/api/v1/content")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["slug"] == approved.slug
        assert payload[0]["status"] == ContentStatus.APPROVED.value

        detail_response = client.get(f"/api/v1/content/{draft.slug}")
        assert detail_response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_generate_draft_from_case_context():
    testing_session_local = build_test_session()
    session = testing_session_local()
    try:
        service = KnowledgeBaseService(session)
        content = asyncio.run(
            service.generate_draft_answer(
                question="What should I expect at my first felony court date?",
                title="First felony court date",
                content_type=ContentType.GUIDE,
                charge_type="DRUG",
                source_context={
                    "attorney_profile": {"name": "Aaron Brockler", "background": ["Former prosecutor"]},
                    "dataset_summary": {"total_cases": 100, "top_crime_types": [{"crime_type": "DRUG", "cases": 40}]},
                },
                source_metrics={"total_cases": 100},
                citations=["https://www.brocklerlaw.com/aaron-brockler"],
            )
        )

        assert content.status == ContentStatus.DRAFT
        assert content.charge_type == "DRUG"
        assert "Aaron Brockler" in str(content.source_payload)
        assert content.citations == ["https://www.brocklerlaw.com/aaron-brockler"]
    finally:
        session.close()


def test_recommendation_explanation_builder():
    testing_session_local = build_test_session()
    session = testing_session_local()
    try:
        service = KnowledgeBaseService(session)
        payload = service.build_recommendation_explanation(
            judge_id=1,
            prosecutor_id=2,
            charge_type="VIOLENT",
            recommendation={
                "attorney_name": "Aaron Brockler",
                "overall_win_rate": 0.45,
                "matchup_win_rate": 0.52,
                "charge_type_win_rate": 0.49,
                "total_cases": 38,
                "effectiveness_score": 7.8,
                "score_breakdown": {"matchup_score": 20.8, "charge_score": 14.7},
                "coverage_label": "MEDIUM",
            },
        )
        assert payload["coverage_label"] == "MEDIUM"
        assert payload["evidence"]["matchup_win_rate"] == 0.52
        assert payload["summary"].startswith("Aaron Brockler")
        assert payload["key_factors"]
    finally:
        session.close()


def test_review_action_endpoint_transitions_statuses():
    testing_session_local = build_test_session()
    session = testing_session_local()
    try:
        service = KnowledgeBaseService(session)
        content = service.create_draft(
            title="Needs review",
            body="Draft body",
            content_type=ContentType.FAQ,
        )

        def override_get_db():
            db = testing_session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        review_response = client.post(
            f"/api/v1/content/{content.slug}/review",
            json={"action": "under_review", "reviewer_name": "Aaron Brockler"},
        )
        assert review_response.status_code == 200
        assert review_response.json()["status"] == ContentStatus.UNDER_REVIEW.value

        approve_response = client.post(
            f"/api/v1/content/{content.slug}/review",
            json={"action": "approve", "reviewer_name": "Aaron Brockler"},
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["status"] == ContentStatus.APPROVED.value

        invalid_response = client.post(
            f"/api/v1/content/{content.slug}/review",
            json={"action": "invalid", "reviewer_name": "Aaron Brockler"},
        )
        assert invalid_response.status_code == 400
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_export_endpoint_returns_approved_only():
    testing_session_local = build_test_session()
    session = testing_session_local()
    try:
        service = KnowledgeBaseService(session)
        approved = service.create_draft(
            title="Approved for feed",
            body="Approved body",
            content_type=ContentType.FAQ,
        )
        service.approve_content(approved.slug, "Aaron Brockler")
        service.create_draft(
            title="Still draft",
            body="Not approved",
            content_type=ContentType.FAQ,
        )

        def override_get_db():
            db = testing_session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        response = client.get("/api/v1/content/export")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_items"] == 1
        assert payload["items"][0]["slug"] == approved.slug
    finally:
        app.dependency_overrides.clear()
        session.close()

def test_email_review_sequence_sonia_then_aaron():
    testing_session_local = build_test_session()
    session = testing_session_local()
    fake_email = FakeEmailService()

    try:
        service = KnowledgeBaseService(session, email_service=fake_email)
        service.sonia_name = "Sonia"
        service.sonia_email = "sonia@example.com"
        service.aaron_name = "Aaron"
        service.aaron_email = "aaron@example.com"

        content = service.create_draft(
            title="Email workflow draft",
            body="Pending sequence review",
            content_type=ContentType.FAQ,
        )

        submitted = service.review_action(
            slug=content.slug,
            action="submit",
            reviewer_name="Case Team",
        )
        assert submitted is not None
        assert submitted.status == ContentStatus.UNDER_REVIEW
        assert fake_email.sent[-1]["to"] == "sonia@example.com"

        after_sonia = service.review_action(
            slug=content.slug,
            action="approve",
            reviewer_name="Sonia",
        )
        assert after_sonia is not None
        assert after_sonia.status == ContentStatus.UNDER_REVIEW
        assert fake_email.sent[-1]["to"] == "aaron@example.com"

        after_aaron = service.review_action(
            slug=content.slug,
            action="approve",
            reviewer_name="Aaron",
        )
        assert after_aaron is not None
        assert after_aaron.status == ContentStatus.APPROVED
    finally:
        session.close()
