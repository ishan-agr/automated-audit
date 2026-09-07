"""Audit API request/response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class AuditCreate(BaseModel):
    subject_name: str = Field(min_length=1, max_length=255)  # only required field
    subject_email: str | None = None
    subject_phone: str | None = None
    subject_dob: date | None = None  # optional; used for password derivation


class RangeUpdate(BaseModel):
    range_from: date
    range_to: date


class AuditRead(BaseModel):
    id: str
    subject_name: str
    subject_email: str | None
    subject_phone: str | None
    status: str
    range_from: date | None
    range_to: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
