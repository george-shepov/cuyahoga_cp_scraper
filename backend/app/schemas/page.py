from pydantic import BaseModel, Field
from typing import List, Optional


class FAQItem(BaseModel):
    question: str
    answer: str


class SectionBlock(BaseModel):
    heading: str
    body: str
    bullets: List[str] = Field(default_factory=list)


class CTA(BaseModel):
    heading: str
    body: str
    primary_label: str
    primary_href: str
    secondary_label: Optional[str] = None
    secondary_href: Optional[str] = None


class SEOPage(BaseModel):
    slug: str
    title: str
    meta_description: str
    h1: str
    intro: str
    sections: List[SectionBlock]
    faq: List[FAQItem]
    cta: CTA
    related_routes: List[str] = Field(default_factory=list)
