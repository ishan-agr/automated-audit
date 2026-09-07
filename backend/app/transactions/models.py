"""ExtractedTransaction (the durable, immutable extraction cache) + DocumentMeta.

Every report/reconciliation is a pure function of these rows filtered by date, so
changing the audit range regenerates without re-extraction.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Direction(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class ParseSource(str, Enum):
    REGEX = "REGEX"
    SLM = "SLM"
    MANUAL = "MANUAL"


class ExtractedTransaction(SQLModel, table=True):
    __tablename__ = "extracted_transactions"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    audit_id: str = Field(index=True)
    document_id: str = Field(index=True)

    page_num: int | None = Field(default=None)
    row_index: int | None = Field(default=None)

    tran_date: date | None = Field(default=None, index=True)
    value_date: date | None = Field(default=None)

    narration_raw: str = Field(default="")
    direction: str = Field(default=Direction.DEBIT.value)
    amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    balance: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)

    channel: str | None = Field(default=None, index=True)
    txn_subtype: str | None = Field(default=None)
    ref_id: str | None = Field(default=None, index=True)

    counterparty_name: str | None = Field(default=None, index=True)
    source_account: str | None = Field(default=None, index=True)  # for multi-account

    identifiers: dict = Field(default_factory=dict, sa_column=Column(JSON))
    user_label: str | None = Field(default=None, index=True)

    confidence: float = Field(default=0.0)
    parse_source: str = Field(default=ParseSource.REGEX.value)
    # internal-transfer netting flag (set by the reconcile pre-pass, §2.6)
    is_internal_transfer: bool = Field(default=False)
    # overlap-dedup provenance: id of the canonical row this one duplicates
    superseded_by: str | None = Field(default=None)

    raw_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DocumentMeta(SQLModel, table=True):
    """Per-document miscellaneous details — structured header facts + freeform."""

    __tablename__ = "document_meta"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    document_id: str = Field(index=True, unique=True)
    audit_id: str = Field(index=True)
    kv: dict = Field(default_factory=dict, sa_column=Column(JSON))
    freeform: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
