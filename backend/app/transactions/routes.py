"""Transaction structuring + listing routes."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.transactions import service

router = APIRouter(prefix="/api/v1/audits/{audit_id}", tags=["transactions"])


class TransactionRead(BaseModel):
    id: str
    document_id: str
    page_num: int | None
    tran_date: date | None
    narration_raw: str
    direction: str
    amount: Decimal
    balance: Decimal | None
    channel: str | None
    txn_subtype: str | None
    ref_id: str | None
    counterparty_name: str | None
    source_account: str | None
    identifiers: dict
    user_label: str | None
    confidence: float
    parse_source: str
    is_internal_transfer: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/documents/{doc_id}/structure")
def structure_document(
    audit_id: str, doc_id: str, session: Session = Depends(get_session)
):
    """Run Docling table extraction + deterministic parse → persist transactions.
    Synchronous (Docling is heavy); call once per document after extraction."""
    try:
        return service.structure_document(session, doc_id)
    except service.DocumentNotFound as exc:
        raise HTTPException(404, "document not found") from exc


@router.get("/transactions", response_model=list[TransactionRead])
def list_transactions(audit_id: str, session: Session = Depends(get_session)):
    return service.list_transactions(session, audit_id)
