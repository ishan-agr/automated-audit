"""AuditDocument — a single source file attached to an audit (bank PDF, UPI
CSV/XLSX, …). Password-related fields track the unlock gate; the password itself
is never stored on the document row (only optionally on a BankCredential).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlmodel import Field, SQLModel


class DocKind(str, Enum):
    BANK_STATEMENT = "BANK_STATEMENT"
    UPI_EXPORT = "UPI_EXPORT"
    UNKNOWN = "UNKNOWN"


class PasswordStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"  # file wasn't encrypted
    LOCKED = "LOCKED"  # encrypted, awaiting a working password
    UNLOCKED = "UNLOCKED"  # decrypted, ready for extraction


class DocStatus(str, Enum):
    PENDING = "PENDING"
    LOCKED = "LOCKED"  # blocked on a password
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    PARSED = "PARSED"
    READY = "READY"
    FAILED = "FAILED"


class AuditDocument(SQLModel, table=True):
    __tablename__ = "audit_documents"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    audit_id: str = Field(index=True)
    file_id: str = Field(index=True)  # dedupe by SHA-256 (of the ORIGINAL bytes)
    filename: str = Field(max_length=255)

    doc_kind: str = Field(default=DocKind.UNKNOWN.value)
    bank: str = Field(default="UNKNOWN", index=True)  # bank_profiles.passwords.Bank

    status: str = Field(default=DocStatus.PENDING.value, index=True)

    # Password gate. `password_status` starts NOT_REQUIRED and flips to LOCKED
    # the moment the uploader sees `is_encrypted`. It becomes UNLOCKED once a
    # candidate opens it. `unlocked_with_saved_credential` records whether a
    # stored bank credential (vs. a typed password) did the unlocking — useful
    # UX signal ("used your saved HDFC password").
    is_encrypted: bool = Field(default=False)
    password_status: str = Field(default=PasswordStatus.NOT_REQUIRED.value)
    unlocked_with_saved_credential: bool = Field(default=False)

    page_count: int | None = Field(default=None)
    pages_extracted: int | None = Field(default=None)
    pages_total: int | None = Field(default=None)
    error_message: str | None = Field(default=None, max_length=2000)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
