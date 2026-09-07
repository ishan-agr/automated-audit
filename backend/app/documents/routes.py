"""Document ingest routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from app.bank_profiles.passwords import Bank
from app.core.db import get_session
from app.documents import service
from app.documents.models import DocKind
from app.documents.schemas import DocumentRead, UnlockRequest
from app.documents.service import AuditNotFound, DuplicateDocument
from app.extraction.pdf_password import PdfPasswordRequired

router = APIRouter(prefix="/api/v1/audits/{audit_id}/documents", tags=["documents"])


def _bank(value: str) -> Bank:
    try:
        return Bank(value.upper())
    except ValueError as exc:
        raise HTTPException(422, f"unknown bank '{value}'") from exc


def _kind(value: str) -> DocKind:
    try:
        return DocKind(value.upper())
    except ValueError as exc:
        raise HTTPException(422, f"unknown doc_kind '{value}'") from exc


@router.post("", response_model=DocumentRead, status_code=202)
async def upload_document(
    audit_id: str,
    file: UploadFile = File(...),
    bank: str = Form("UNKNOWN"),
    doc_kind: str = Form("UNKNOWN"),
    password: str | None = Form(None),
    save_credential: bool = Form(False),
    session: Session = Depends(get_session),
):
    try:
        return await service.upload_document(
            session,
            audit_id=audit_id,
            filename=file.filename or "upload.pdf",
            file_obj=file.file,
            bank=_bank(bank),
            doc_kind=_kind(doc_kind),
            password=password,
            save_credential=save_credential,
        )
    except AuditNotFound as exc:
        raise HTTPException(404, "audit not found") from exc
    except DuplicateDocument as exc:
        raise HTTPException(
            409, f"identical file already uploaded (doc {exc.existing_id})"
        ) from exc


@router.post("/{doc_id}/unlock", response_model=DocumentRead)
async def unlock_document(
    audit_id: str,
    doc_id: str,
    payload: UnlockRequest,
    session: Session = Depends(get_session),
):
    try:
        return await service.unlock_document(
            session,
            audit_id=audit_id,
            doc_id=doc_id,
            password=payload.password,
            save_credential=payload.save_credential,
        )
    except AuditNotFound as exc:
        raise HTTPException(404, "document not found") from exc
    except PdfPasswordRequired as exc:
        raise HTTPException(422, "password did not unlock the document") from exc


@router.get("", response_model=list[DocumentRead])
def list_documents(audit_id: str, session: Session = Depends(get_session)):
    return service.list_documents(session, audit_id)


@router.get("/{doc_id}", response_model=DocumentRead)
def get_document(audit_id: str, doc_id: str, session: Session = Depends(get_session)):
    doc = service.get_document(session, audit_id, doc_id)
    if doc is None:
        raise HTTPException(404, "document not found")
    return doc
