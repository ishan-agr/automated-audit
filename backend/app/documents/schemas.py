"""Document API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DocumentRead(BaseModel):
    id: str
    audit_id: str
    file_id: str
    filename: str
    doc_kind: str
    bank: str
    status: str
    is_encrypted: bool
    password_status: str
    unlocked_with_saved_credential: bool
    page_count: int | None
    pages_extracted: int | None
    pages_total: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UnlockRequest(BaseModel):
    password: str
    save_credential: bool = False  # remember this password against the bank
    label: str | None = None
