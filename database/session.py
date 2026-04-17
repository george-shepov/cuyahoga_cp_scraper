"""Database session helpers for API and local development."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.analytics_models import Base as AnalyticsBase
from database.models_postgres import Base


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./analytics.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create tables for local development and tests.

    The analytics metadata is created on a best-effort basis because this
    repository does not yet provide a full production database bootstrap layer.
    """
    Base.metadata.create_all(bind=engine)
    try:
        AnalyticsBase.metadata.create_all(bind=engine)
    except Exception:
        # Analytics tables are still partially scaffolded in this repository.
        pass
