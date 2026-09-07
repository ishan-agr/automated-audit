"""Audit — the unit of work. Owns multiple sources + a mutable date range.

Optional personal fields (dob/pan/customer_id) are here because they double as
statement-password derivation inputs; they are only collected if the user wants
password auto-derivation and are otherwise null. `subject_name` is the only
required field at initiation.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlmodel import Field, SQLModel

from app.audit.ids import new_audit_id


class AuditStatus:
    DRAFT = "DRAFT"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    GENERATED = "GENERATED"
    FAILED = "FAILED"


class Audit(SQLModel, table=True):
    __tablename__ = "audits"

    id: str = Field(default_factory=new_audit_id, primary_key=True)

    subject_name: str = Field(index=True)  # required
    subject_email: str | None = Field(default=None)
    subject_phone: str | None = Field(default=None)

    # Optional; used only for password derivation (kept minimal, not sensitive
    # doc content). PAN/customer_id are not persisted in plaintext if the user
    # declines derivation — they live in an encrypted BankCredential instead.
    subject_dob: date | None = Field(default=None)

    status: str = Field(default=AuditStatus.DRAFT, index=True)
    range_from: date | None = Field(default=None)
    range_to: date | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
