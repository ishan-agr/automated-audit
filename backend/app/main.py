"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from app.audit.routes import router as audit_router
from app.core.db import init_db
from app.documents.routes import router as documents_router
from app.report.routes import router as report_router
from app.transactions.routes import router as transactions_router


def create_app() -> FastAPI:
    app = FastAPI(title="Automated Audit", version="0.1.0")
    init_db()  # idempotent create_all; ready before the first request

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(audit_router)
    app.include_router(documents_router)
    app.include_router(transactions_router)
    app.include_router(report_router)
    return app


app = create_app()
