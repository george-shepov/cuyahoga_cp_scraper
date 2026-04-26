from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.schemas.content import ContentItemCreate, ContentItemUpdate, ContentListResponse, ContentItemResponse
from database.models_postgres import KnowledgeContent, ContentStatus, ContentType


# ── helpers ──────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug[:160]


def _to_response(item: KnowledgeContent) -> ContentItemResponse:
    return ContentItemResponse(
        id=item.id,
        slug=item.slug,
        title=item.title,
        question=item.question,
        summary=item.summary,
        body=item.body,
        content_type=item.content_type.value if hasattr(item.content_type, "value") else item.content_type,
        status=item.status.value if hasattr(item.status, "value") else item.status,
        audience=item.audience or "public",
        charge_type=item.charge_type,
        tags=item.tags or [],
        reviewer_name=item.reviewer_name,
        reviewed_at=item.reviewed_at,
        approved_at=item.approved_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


# ── list ─────────────────────────────────────────────────────────────────────

def list_content(
    db: Session,
    status: Optional[str] = None,
    content_type: Optional[str] = None,
    limit: int = 200,
) -> ContentListResponse:
    q = db.query(KnowledgeContent)
    if status:
        q = q.filter(KnowledgeContent.status == status)
    if content_type:
        q = q.filter(KnowledgeContent.content_type == content_type)
    items = q.order_by(KnowledgeContent.updated_at.desc()).limit(limit).all()

    # counts across all statuses (ignore filters for counts)
    all_q = db.query(KnowledgeContent)
    all_items = all_q.all()
    counts: dict[str, int] = {"DRAFT": 0, "UNDER_REVIEW": 0, "APPROVED": 0, "ARCHIVED": 0}
    for it in all_items:
        s = it.status.value if hasattr(it.status, "value") else it.status
        counts[s] = counts.get(s, 0) + 1

    return ContentListResponse(
        items=[_to_response(i) for i in items],
        total=len(all_items),
        draft_count=counts["DRAFT"],
        review_count=counts["UNDER_REVIEW"],
        approved_count=counts["APPROVED"],
        archived_count=counts["ARCHIVED"],
    )


# ── create ────────────────────────────────────────────────────────────────────

def create_content(db: Session, payload: ContentItemCreate) -> ContentItemResponse:
    slug = payload.slug or _slugify(payload.title)
    # ensure uniqueness
    existing = db.query(KnowledgeContent).filter(KnowledgeContent.slug == slug).first()
    if existing:
        slug = f"{slug}-{int(datetime.now().timestamp())}"

    item = KnowledgeContent(
        slug=slug,
        title=payload.title,
        question=payload.question,
        summary=payload.summary,
        body=payload.body,
        content_type=payload.content_type,
        status=ContentStatus.DRAFT,
        audience=payload.audience,
        charge_type=payload.charge_type,
        tags=payload.tags or [],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_response(item)


# ── update / status transitions ───────────────────────────────────────────────

def update_content(db: Session, item_id: int, payload: ContentItemUpdate) -> ContentItemResponse | None:
    item = db.query(KnowledgeContent).filter(KnowledgeContent.id == item_id).first()
    if not item:
        return None

    now = datetime.now(tz=timezone.utc)

    if payload.title is not None:
        item.title = payload.title
    if payload.question is not None:
        item.question = payload.question
    if payload.summary is not None:
        item.summary = payload.summary
    if payload.body is not None:
        item.body = payload.body
    if payload.tags is not None:
        item.tags = payload.tags
    if payload.reviewer_name is not None:
        item.reviewer_name = payload.reviewer_name

    if payload.status is not None:
        new_status = payload.status
        item.status = new_status
        if new_status in ("UNDER_REVIEW", "APPROVED"):
            item.reviewed_at = now
        if new_status == "APPROVED":
            item.approved_at = now

    item.updated_at = now
    db.commit()
    db.refresh(item)
    return _to_response(item)


# ── delete ────────────────────────────────────────────────────────────────────

def delete_content(db: Session, item_id: int) -> bool:
    item = db.query(KnowledgeContent).filter(KnowledgeContent.id == item_id).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


# ── seed ──────────────────────────────────────────────────────────────────────

SEED_ITEMS = [
    # APPROVED — already on public page
    {
        "slug": "faq-what-to-do-after-ovi-arrest",
        "title": "What should I do first after an OVI arrest?",
        "question": "What should I do first after an OVI arrest?",
        "body": "Start by collecting every paper you received and confirming the next date or deadline shown on your documents.",
        "content_type": "FAQ",
        "status": "APPROVED",
    },
    {
        "slug": "faq-ovi-dui-ohio-same",
        "title": "Do OVI and DUI mean the same thing in Ohio?",
        "question": "Do OVI and DUI mean the same thing in Ohio?",
        "body": "Most people search for DUI, but Ohio statutes and local courts usually use the term OVI.",
        "content_type": "FAQ",
        "status": "APPROVED",
    },
    {
        "slug": "faq-first-offense-ovi",
        "title": "What if this is my first offense?",
        "question": "What if this is my first offense?",
        "body": "A first offense is still serious because license issues and court exposure can start immediately.",
        "content_type": "FAQ",
        "status": "APPROVED",
    },
    # UNDER_REVIEW — candidates for promotion
    {
        "slug": "faq-als-appeal-deadline",
        "title": "How long do I have to appeal my ALS suspension?",
        "question": "How long do I have to appeal my ALS suspension?",
        "body": "Ohio gives you 15 days from the date of arrest to request an ALS hearing. Missing that window means the suspension takes full effect.",
        "content_type": "FAQ",
        "status": "UNDER_REVIEW",
    },
    {
        "slug": "faq-can-i-drive-to-work",
        "title": "Can I still drive to work after an OVI arrest?",
        "question": "Can I still drive to work after an OVI arrest?",
        "body": "That depends on the type of suspension exposure and what the court allows. Limited driving privileges may be available.",
        "content_type": "FAQ",
        "status": "UNDER_REVIEW",
    },
    {
        "slug": "faq-refusal-chemical-test",
        "title": "What happens if I refused the chemical test?",
        "question": "What happens if I refused the chemical test?",
        "body": "Refusal triggers an immediate ALS and can change your exposure. It may also affect whether certain defenses are available.",
        "content_type": "FAQ",
        "status": "UNDER_REVIEW",
    },
    {
        "slug": "faq-ovi-prior-10-years",
        "title": "Does a prior OVI within 10 years change the stakes?",
        "question": "Does a prior OVI within 10 years change the stakes?",
        "body": "Yes. Ohio's look-back window is 10 years. A prior within that window escalates minimum penalties significantly.",
        "content_type": "FAQ",
        "status": "UNDER_REVIEW",
    },
    # DRAFT — rough ideas, not ready
    {
        "slug": "faq-cdl-ovi-consequences",
        "title": "I hold a CDL — how bad is an OVI for me?",
        "question": "I hold a CDL — how bad is an OVI for me?",
        "body": "CDL holders face stricter BAC limits and disqualification rules. Even a first offense can end a commercial driving career.",
        "content_type": "FAQ",
        "status": "DRAFT",
    },
    {
        "slug": "faq-field-sobriety-test",
        "title": "Are field sobriety tests required in Ohio?",
        "question": "Are field sobriety tests required in Ohio?",
        "body": "No. Ohio drivers are not legally required to perform field sobriety tests, but refusal can be noted by the officer.",
        "content_type": "FAQ",
        "status": "DRAFT",
    },
    {
        "slug": "faq-breath-test-accuracy",
        "title": "Can the breath test result be challenged?",
        "question": "Can the breath test result be challenged?",
        "body": "Yes. Calibration records, officer training, and test timing are all potential challenge points.",
        "content_type": "FAQ",
        "status": "DRAFT",
    },
]


def seed_content(db: Session) -> int:
    """Insert seed items that don't already exist. Returns count inserted."""
    inserted = 0
    for item in SEED_ITEMS:
        existing = db.query(KnowledgeContent).filter(KnowledgeContent.slug == item["slug"]).first()
        if existing:
            continue
        status_val = item.pop("status", "DRAFT")
        row = KnowledgeContent(**item, status=status_val, audience="public", tags=[])
        db.add(row)
        inserted += 1
    if inserted:
        db.commit()
    return inserted
