from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.pages import router as pages_router
from app.api.routes.case_analysis import router as case_analysis_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.billing import router as billing_router
from database.session import init_db

app = FastAPI(title="OVI Content Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pages_router, prefix="/api")
app.include_router(case_analysis_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(billing_router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
