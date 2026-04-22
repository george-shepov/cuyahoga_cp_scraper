from fastapi import APIRouter, HTTPException

from app.schemas.page import SEOPage
from app.services.page_registry import PAGE_REGISTRY

router = APIRouter(tags=["pages"])


@router.get("/pages", response_model=list[SEOPage])
def list_pages() -> list[SEOPage]:
    return list(PAGE_REGISTRY.values())


@router.get("/pages/{slug}", response_model=SEOPage)
def get_page(slug: str) -> SEOPage:
    page = PAGE_REGISTRY.get(slug)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page
