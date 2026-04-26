from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.page import FAQItem, SEOPage
from app.services.page_registry import PAGE_REGISTRY
from database.models_postgres import ContentStatus, ContentType, KnowledgeContent
from database.session import SessionLocal

router = APIRouter(tags=["pages"])


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _approved_faq(db: Session) -> list[FAQItem]:
    """Return only APPROVED FAQ items from the DB, ordered by approved_at."""
    rows = (
        db.query(KnowledgeContent)
        .filter(
            KnowledgeContent.status == ContentStatus.APPROVED,
            KnowledgeContent.content_type == ContentType.FAQ,
        )
        .order_by(KnowledgeContent.approved_at.asc())
        .all()
    )
    return [
        FAQItem(question=r.question or r.title, answer=r.body)
        for r in rows
    ]


@router.get("/pages", response_model=list[SEOPage])
def list_pages(db: Session = Depends(get_db)) -> list[SEOPage]:
    faq = _approved_faq(db)
    pages = []
    for page in PAGE_REGISTRY.values():
        # Replace static FAQ with live approved items if any exist
        pages.append(page.model_copy(update={"faq": faq}) if faq else page)
    return pages


@router.get("/pages/{slug}", response_model=SEOPage)
def get_page(slug: str, db: Session = Depends(get_db)) -> SEOPage:
    page = PAGE_REGISTRY.get(slug)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    approved_faq = _approved_faq(db)
    # Only override if DB has approved items — fall back to static registry otherwise
    if approved_faq:
        return page.model_copy(update={"faq": approved_faq})
    return page
