"""Audit lifecycle routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.audit import service
from app.audit.schemas import AuditCreate, AuditRead, RangeUpdate
from app.core.db import get_session

router = APIRouter(prefix="/api/v1/audits", tags=["audits"])


@router.post("", response_model=AuditRead, status_code=201)
def create_audit(payload: AuditCreate, session: Session = Depends(get_session)):
    return service.create_audit(session, payload)


@router.get("", response_model=list[AuditRead])
def list_audits(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return service.list_audits(session, limit=limit, offset=offset)


@router.get("/{audit_id}", response_model=AuditRead)
def get_audit(audit_id: str, session: Session = Depends(get_session)):
    audit = service.get_audit(session, audit_id)
    if audit is None:
        raise HTTPException(404, "audit not found")
    return audit


@router.patch("/{audit_id}/range", response_model=AuditRead)
def update_range(
    audit_id: str, payload: RangeUpdate, session: Session = Depends(get_session)
):
    if payload.range_to < payload.range_from:
        raise HTTPException(422, "range_to must be on/after range_from")
    audit = service.update_range(session, audit_id, payload.range_from, payload.range_to)
    if audit is None:
        raise HTTPException(404, "audit not found")
    return audit
