from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_current_user
from app.schemas.content import (
    ContentItemCreate,
    ContentItemUpdate,
    ContentItemResponse,
    ContentListResponse,
)
from app.services.content_service import (
    list_content,
    create_content,
    update_content,
    delete_content,
    seed_content,
)
from database.session import SessionLocal

router = APIRouter(tags=["content"], dependencies=[Depends(get_current_user)])


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/content", response_model=ContentListResponse)
def get_content(
    status: Optional[str] = None,
    content_type: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> ContentListResponse:
    """
    List knowledge content items.

    - **status**: filter by DRAFT | UNDER_REVIEW | APPROVED | ARCHIVED
    - **content_type**: filter by FAQ | GUIDE | etc.
    """
    return list_content(db, status=status, content_type=content_type, limit=limit)


@router.post("/content", response_model=ContentItemResponse, status_code=201)
def post_content(payload: ContentItemCreate, db: Session = Depends(get_db)) -> ContentItemResponse:
    return create_content(db, payload)


@router.patch("/content/{item_id}", response_model=ContentItemResponse)
def patch_content(item_id: int, payload: ContentItemUpdate, db: Session = Depends(get_db)) -> ContentItemResponse:
    result = update_content(db, item_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Content item {item_id} not found")
    return result


@router.delete("/content/{item_id}", status_code=204)
def remove_content(item_id: int, db: Session = Depends(get_db)) -> None:
    ok = delete_content(db, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Content item {item_id} not found")


@router.post("/content/seed", status_code=200)
def run_seed(db: Session = Depends(get_db)) -> dict[str, int]:
    """Insert default FAQ seed items (idempotent — skips existing slugs)."""
    inserted = seed_content(db)
    return {"inserted": inserted}
