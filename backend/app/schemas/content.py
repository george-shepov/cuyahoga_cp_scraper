from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


ContentStatusLiteral = Literal["DRAFT", "UNDER_REVIEW", "APPROVED", "ARCHIVED"]
ContentTypeLiteral = Literal["FAQ", "GUIDE", "JUDGE_PROFILE", "PROSECUTOR_PROFILE", "RECOMMENDATION_EXPLANATION"]


class ContentItemBase(BaseModel):
    slug: str
    title: str
    question: Optional[str] = None
    summary: Optional[str] = None
    body: str
    content_type: ContentTypeLiteral = "FAQ"
    audience: str = "public"
    charge_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ContentItemCreate(ContentItemBase):
    pass


class ContentItemUpdate(BaseModel):
    title: Optional[str] = None
    question: Optional[str] = None
    summary: Optional[str] = None
    body: Optional[str] = None
    status: Optional[ContentStatusLiteral] = None
    tags: Optional[List[str]] = None
    reviewer_name: Optional[str] = None


class ContentItemResponse(ContentItemBase):
    id: int
    status: ContentStatusLiteral
    reviewer_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContentListResponse(BaseModel):
    items: List[ContentItemResponse]
    total: int
    draft_count: int
    review_count: int
    approved_count: int
    archived_count: int
