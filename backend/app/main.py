import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.pages import router as pages_router
from app.api.routes.case_analysis import router as case_analysis_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.billing import router as billing_router
from app.api.routes.case_intelligence import router as case_intelligence_router
from app.api.routes.content import router as content_router
from database.session import init_db

app = FastAPI(title="OVI Content Engine")

# Allow only the local dev server and the production domain.
# Override via ALLOWED_ORIGINS env var (comma-separated).
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:5174,https://prosecutordefense.com,https://www.prosecutordefense.com",
)
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(pages_router, prefix="/api")
app.include_router(case_analysis_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(case_intelligence_router, prefix="/api")
app.include_router(content_router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    from app.services.content_service import seed_content
    from database.session import SessionLocal
    db = SessionLocal()
    try:
        seed_content(db)
    finally:
        db.close()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
