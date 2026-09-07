"""Report + generation routes. Reconciliation is produced by `generate`, not a
separate endpoint (LLD §5.4/§5.6)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.report import service

router = APIRouter(prefix="/api/v1/audits/{audit_id}", tags=["report"])


class NodeIn(BaseModel):
    id: str
    kind: str
    config: dict = {}
    ui: dict = {}


class EdgeIn(BaseModel):
    source: str
    target: str
    target_port: str = "in"


class GraphIn(BaseModel):
    name: str | None = None
    nodes: list[NodeIn] = []
    edges: list[EdgeIn] = []


class GenerateIn(BaseModel):
    range_from: date | None = None
    range_to: date | None = None


@router.get("/report")
def get_report(audit_id: str, session: Session = Depends(get_session)):
    return service.load_graph(session, audit_id)


@router.put("/report")
def put_report(audit_id: str, graph: GraphIn, session: Session = Depends(get_session)):
    try:
        return service.save_graph(
            session,
            audit_id,
            nodes=[n.model_dump() for n in graph.nodes],
            edges=[e.model_dump() for e in graph.edges],
            name=graph.name,
        )
    except service.AuditNotFound as exc:
        raise HTTPException(404, "audit not found") from exc
    except service.InvalidGraph as exc:
        raise HTTPException(422, f"invalid graph: {exc}") from exc


@router.post("/generate")
def generate(
    audit_id: str,
    payload: GenerateIn | None = None,
    session: Session = Depends(get_session),
):
    payload = payload or GenerateIn()
    try:
        return service.generate_audit(
            session, audit_id, payload.range_from, payload.range_to
        )
    except service.AuditNotFound as exc:
        raise HTTPException(404, "audit not found") from exc
