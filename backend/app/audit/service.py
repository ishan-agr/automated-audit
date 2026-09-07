"""Audit lifecycle business logic."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlmodel import Session, select

from app.audit.models import Audit
from app.audit.schemas import AuditCreate


def create_audit(session: Session, payload: AuditCreate) -> Audit:
    audit = Audit(
        subject_name=payload.subject_name,
        subject_email=payload.subject_email,
        subject_phone=payload.subject_phone,
        subject_dob=payload.subject_dob,
    )
    session.add(audit)
    session.commit()
    session.refresh(audit)
    return audit


def get_audit(session: Session, audit_id: str) -> Audit | None:
    return session.get(Audit, audit_id)


def list_audits(session: Session, limit: int = 50, offset: int = 0) -> list[Audit]:
    stmt = select(Audit).order_by(Audit.created_at.desc()).offset(offset).limit(limit)
    return list(session.exec(stmt))


def update_range(
    session: Session, audit_id: str, range_from: date, range_to: date
) -> Audit | None:
    audit = session.get(Audit, audit_id)
    if audit is None:
        return None
    audit.range_from = range_from
    audit.range_to = range_to
    audit.updated_at = datetime.now(UTC)
    session.add(audit)
    session.commit()
    session.refresh(audit)
    # NOTE: in Phase 2.5+ this also triggers generate_audit(range) (reconcile +
    # report) over the cache — pure re-eval, never re-extraction.
    return audit
