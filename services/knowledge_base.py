"""Knowledge base service for reviewed content and recommendation explanations."""

from __future__ import annotations

import copy
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models_postgres import (
    ContentStatus,
    ContentType,
    KnowledgeContent,
    RecommendationExplanationSnapshot,
)
from services.email_service import EmailService
from services.llm_service import LITELLM_AVAILABLE, LLMProvider, LLMService


def slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return base or f"draft-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


class KnowledgeBaseService:
    """Create, review, and retrieve knowledge content."""

    def __init__(
        self,
        db_session: Session,
        llm_service: Optional[LLMService] = None,
        email_service: Optional[EmailService] = None,
    ):
        self.db = db_session
        self.llm_service = llm_service
        self.email_service = email_service or EmailService()

        self.sonia_name = os.getenv("REVIEW_SONIA_NAME", "Sonia")
        self.sonia_email = os.getenv("REVIEW_SONIA_EMAIL")
        self.aaron_name = os.getenv("REVIEW_AARON_NAME", "Aaron")
        self.aaron_email = os.getenv("REVIEW_AARON_EMAIL")

    def list_content(
        self,
        *,
        status: ContentStatus = ContentStatus.APPROVED,
        content_type: Optional[ContentType] = None,
        charge_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[KnowledgeContent]:
        query = self.db.query(KnowledgeContent).filter(KnowledgeContent.status == status)
        if content_type:
            query = query.filter(KnowledgeContent.content_type == content_type)
        if charge_type:
            query = query.filter(KnowledgeContent.charge_type == charge_type)
        return query.order_by(KnowledgeContent.updated_at.desc()).limit(limit).all()

    def get_content_by_slug(
        self,
        slug: str,
        *,
        status: ContentStatus = ContentStatus.APPROVED,
    ) -> Optional[KnowledgeContent]:
        return self.db.query(KnowledgeContent).filter(
            KnowledgeContent.slug == slug,
            KnowledgeContent.status == status,
        ).first()

    def get_content_any_status(self, slug: str) -> Optional[KnowledgeContent]:
        return self.db.query(KnowledgeContent).filter(KnowledgeContent.slug == slug).first()

    def create_draft(
        self,
        *,
        title: str,
        body: str,
        content_type: ContentType,
        question: Optional[str] = None,
        summary: Optional[str] = None,
        audience: str = "public",
        charge_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source_payload: Optional[Dict[str, Any]] = None,
        source_metrics: Optional[Dict[str, Any]] = None,
        citations: Optional[List[str]] = None,
        slug: Optional[str] = None,
        ai_provider: Optional[str] = None,
        ai_model: Optional[str] = None,
        prompt_version: str = "kb-v1",
    ) -> KnowledgeContent:
        content = KnowledgeContent(
            slug=self._unique_slug(slug or slugify(title)),
            title=title,
            question=question,
            summary=summary,
            body=body,
            content_type=content_type,
            status=ContentStatus.DRAFT,
            audience=audience,
            charge_type=charge_type,
            tags=tags or [],
            source_payload=source_payload or {},
            source_metrics=source_metrics or {},
            citations=citations or [],
            ai_provider=ai_provider,
            ai_model=ai_model,
            prompt_version=prompt_version,
        )
        self.db.add(content)
        self.db.commit()
        self.db.refresh(content)
        return content

    def mark_under_review(self, slug: str, reviewer_name: str) -> Optional[KnowledgeContent]:
        content = self.db.query(KnowledgeContent).filter(KnowledgeContent.slug == slug).first()
        if not content:
            return None
        content.status = ContentStatus.UNDER_REVIEW
        content.reviewer_name = reviewer_name
        content.reviewed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(content)
        return content

    def approve_content(self, slug: str, reviewer_name: str) -> Optional[KnowledgeContent]:
        content = self.db.query(KnowledgeContent).filter(KnowledgeContent.slug == slug).first()
        if not content:
            return None
        content.status = ContentStatus.APPROVED
        content.reviewer_name = reviewer_name
        content.reviewed_at = datetime.utcnow()
        content.approved_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(content)
        return content

    def archive_content(self, slug: str, reviewer_name: str) -> Optional[KnowledgeContent]:
        content = self.db.query(KnowledgeContent).filter(KnowledgeContent.slug == slug).first()
        if not content:
            return None
        content.status = ContentStatus.ARCHIVED
        content.reviewer_name = reviewer_name
        content.reviewed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(content)
        return content

    def review_action(
        self,
        *,
        slug: str,
        action: str,
        reviewer_name: str,
    ) -> Optional[KnowledgeContent]:
        normalized = action.strip().lower()
        if normalized in {"submit", "submit_for_review"}:
            return self.submit_for_email_review(slug, reviewer_name)
        if normalized == "under_review":
            return self.mark_under_review(slug, reviewer_name)
        if normalized == "approve":
            return self.progress_email_approval(slug, reviewer_name)
        if normalized == "archive":
            return self.archive_content(slug, reviewer_name)
        raise ValueError(f"Unsupported review action: {action}")

    def submit_for_email_review(self, slug: str, submitted_by: str) -> Optional[KnowledgeContent]:
        content = self.get_content_any_status(slug)
        if not content:
            return None

        workflow = {
            "submitted_by": submitted_by,
            "submitted_at": datetime.utcnow().isoformat(),
            "sequence": [
                {"stage": "sonia", "name": self.sonia_name, "email": self.sonia_email, "approved": False},
                {"stage": "aaron", "name": self.aaron_name, "email": self.aaron_email, "approved": False},
            ],
            "current_stage": "sonia",
        }

        source_payload = dict(content.source_payload or {})
        source_payload["review_workflow"] = workflow
        content.source_payload = source_payload
        content.status = ContentStatus.UNDER_REVIEW
        content.reviewer_name = submitted_by
        content.reviewed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(content)

        self._notify_stage_reviewer(content, stage="sonia")
        return content

    def progress_email_approval(self, slug: str, reviewer_name: str) -> Optional[KnowledgeContent]:
        content = self.get_content_any_status(slug)
        if not content:
            return None

        source_payload = copy.deepcopy(content.source_payload or {})
        workflow = copy.deepcopy(source_payload.get("review_workflow"))

        if not workflow:
            # Backward compatibility for simple approval flow.
            return self.approve_content(slug, reviewer_name)

        current_stage = workflow.get("current_stage")
        sequence = workflow.get("sequence", [])

        if current_stage == "sonia":
            self._mark_stage_approved(sequence, "sonia", reviewer_name)
            workflow["current_stage"] = "aaron"
            source_payload["review_workflow"] = workflow
            content.source_payload = source_payload
            content.status = ContentStatus.UNDER_REVIEW
            content.reviewer_name = reviewer_name
            content.reviewed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(content)
            self._notify_stage_reviewer(content, stage="aaron")
            return content

        if current_stage == "aaron":
            self._mark_stage_approved(sequence, "aaron", reviewer_name)
            workflow["current_stage"] = "completed"
            source_payload["review_workflow"] = workflow
            content.source_payload = source_payload
            content.status = ContentStatus.APPROVED
            content.reviewer_name = reviewer_name
            content.reviewed_at = datetime.utcnow()
            content.approved_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(content)
            return content

        raise ValueError("Review workflow is not in an approvable state")

    def _mark_stage_approved(self, sequence: List[Dict[str, Any]], stage: str, reviewer_name: str) -> None:
        for item in sequence:
            if item.get("stage") == stage:
                item["approved"] = True
                item["approved_by"] = reviewer_name
                item["approved_at"] = datetime.utcnow().isoformat()
                return

    def _notify_stage_reviewer(self, content: KnowledgeContent, *, stage: str) -> Dict[str, Any]:
        if stage == "sonia":
            recipient_name = self.sonia_name
            recipient_email = self.sonia_email
            action_instruction = (
                f"POST /api/v1/content/{content.slug}/review with action=approve and reviewer_name={self.sonia_name}"
            )
            subject = f"[Review Needed] {content.title}"
        else:
            recipient_name = self.aaron_name
            recipient_email = self.aaron_email
            action_instruction = (
                f"POST /api/v1/content/{content.slug}/review with action=approve and reviewer_name={self.aaron_name}"
            )
            subject = f"[Final Approval Needed] {content.title}"

        body = (
            f"Hi {recipient_name},\n\n"
            f"A knowledge-base draft is ready for your review stage ({stage}).\n\n"
            f"Title: {content.title}\n"
            f"Slug: {content.slug}\n"
            f"Question: {content.question or 'N/A'}\n\n"
            f"To approve this stage: {action_instruction}\n\n"
            "If edits are needed, keep the content in draft/review and update before approval.\n"
        )

        return self.email_service.send_email(
            to_email=recipient_email,
            subject=subject,
            body=body,
        )

    def export_approved_content(self, *, limit: int = 1000) -> List[Dict[str, Any]]:
        items = self.list_content(status=ContentStatus.APPROVED, limit=limit)
        return [
            {
                "slug": item.slug,
                "title": item.title,
                "question": item.question,
                "summary": item.summary,
                "body": item.body,
                "content_type": item.content_type.value,
                "charge_type": item.charge_type,
                "tags": item.tags or [],
                "citations": item.citations or [],
                "reviewer_name": item.reviewer_name,
                "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
                "approved_at": item.approved_at.isoformat() if item.approved_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in items
        ]

    def build_recommendation_explanation(
        self,
        *,
        judge_id: int,
        prosecutor_id: int,
        charge_type: str,
        recommendation: Dict[str, Any],
    ) -> Dict[str, Any]:
        score_breakdown = recommendation.get("score_breakdown", {})
        explanation_points = recommendation.get("key_factors") or self._fallback_factors(recommendation)
        evidence = {
            "overall_win_rate": recommendation.get("overall_win_rate"),
            "matchup_win_rate": recommendation.get("matchup_win_rate"),
            "charge_type_win_rate": recommendation.get("charge_type_win_rate"),
            "total_cases": recommendation.get("total_cases"),
            "effectiveness_score": recommendation.get("effectiveness_score"),
            "score_breakdown": score_breakdown,
        }

        summary = recommendation.get("explanation_preview") or (
            f"{recommendation.get('attorney_name', 'This attorney')} ranks strongly for a "
            f"{charge_type} matter in the judge {judge_id} / prosecutor {prosecutor_id} matchup "
            f"because the historical matchup data, charge-type record, and overall effectiveness all support the recommendation."
        )

        return {
            "summary": summary,
            "key_factors": explanation_points,
            "evidence": evidence,
            "coverage_label": recommendation.get("coverage_label", "LIMITED"),
        }

    def save_recommendation_explanation(
        self,
        *,
        judge_id: int,
        prosecutor_id: int,
        attorney_id: int,
        charge_type: str,
        explanation_payload: Dict[str, Any],
        content_id: Optional[int] = None,
    ) -> RecommendationExplanationSnapshot:
        snapshot = RecommendationExplanationSnapshot(
            content_id=content_id,
            judge_id=judge_id,
            prosecutor_id=prosecutor_id,
            attorney_id=attorney_id,
            charge_type=charge_type,
            explanation_summary=explanation_payload["summary"],
            explanation_points=explanation_payload["key_factors"],
            evidence=explanation_payload["evidence"],
            confidence_label=explanation_payload["coverage_label"],
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    async def generate_draft_answer(
        self,
        *,
        question: str,
        content_type: ContentType,
        title: Optional[str] = None,
        source_context: Optional[Dict[str, Any]] = None,
        source_metrics: Optional[Dict[str, Any]] = None,
        citations: Optional[List[str]] = None,
        charge_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> KnowledgeContent:
        draft = await self._generate_with_fallback(
            question=question,
            content_type=content_type,
            source_context=source_context or {},
        )

        return self.create_draft(
            title=title or draft["title"],
            question=question,
            summary=draft.get("summary"),
            body=draft["body"],
            content_type=content_type,
            charge_type=charge_type,
            tags=tags or [],
            source_payload=source_context or {},
            source_metrics=source_metrics or {},
            citations=citations or [],
            ai_provider=draft.get("provider"),
            ai_model=draft.get("model"),
            prompt_version=draft.get("prompt_version", "kb-v1"),
        )

    async def _generate_with_fallback(
        self,
        *,
        question: str,
        content_type: ContentType,
        source_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self.llm_service is None:
            if LITELLM_AVAILABLE:
                self.llm_service = LLMService(provider=LLMProvider.OLLAMA)
            else:
                self.llm_service = None

        if self.llm_service is not None:
            result = await self.llm_service.generate_answer_draft(
                question=question,
                content_type=content_type.value,
                source_context=source_context,
            )
            if result.get("body"):
                return result

        return {
            "title": question,
            "summary": "Draft answer generated from structured case analytics and pending attorney review.",
            "body": (
                f"Question: {question}\n\n"
                "This draft is a structured starting point built from the existing analytics and recommendation system. "
                "It should be reviewed by counsel before publication. The current source context indicates that the answer "
                "should focus on realistic expectations, likely pressure points, and the practical effect of judge, prosecutor, and charge type."
            ),
            "provider": None,
            "model": None,
            "prompt_version": "kb-v1",
        }

    def _unique_slug(self, base_slug: str) -> str:
        slug = base_slug
        suffix = 1
        while self.db.query(KnowledgeContent).filter(KnowledgeContent.slug == slug).first():
            suffix += 1
            slug = f"{base_slug}-{suffix}"
        return slug

    def _fallback_factors(self, recommendation: Dict[str, Any]) -> List[str]:
        factors = []
        matchup = recommendation.get("matchup_win_rate")
        charge = recommendation.get("charge_type_win_rate")
        overall = recommendation.get("overall_win_rate")
        total_cases = recommendation.get("total_cases")

        if matchup is not None:
            factors.append(f"Matchup win rate for this judge and prosecutor is {matchup:.1%}.")
        if charge is not None:
            factors.append(f"Charge-type win rate is {charge:.1%}.")
        if overall is not None:
            factors.append(f"Overall win rate is {overall:.1%} across {total_cases or 0} cases.")
        return factors