"""Document ingest: streamed upload → dedupe → password gate → dispatch extraction.

The password gate (`app.extraction.pdf_password`) runs BEFORE extraction. An
encrypted doc that can't be opened is parked as `LOCKED`; the user then calls
`unlock_document` with a password (optionally saving it against the bank).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import BinaryIO

from sqlmodel import Session, select

from app.audit.models import Audit
from app.bank_profiles.passwords import Bank, CredentialContext
from app.credentials import service as cred_service
from app.documents.models import AuditDocument, DocKind, DocStatus, PasswordStatus
from app.extraction.pdf_password import (
    PdfPasswordRequired,
    is_encrypted,
    unlock_pdf,
)
from app.extraction.pipeline import run_extraction, work_key
from app.extraction.pool import get_pool
from app.extraction.pypdf_extractor import PypdfPageExtractor
from app.files.hashing import hash_stream
from app.files.storage import get_store


class AuditNotFound(Exception):
    pass


class DuplicateDocument(Exception):
    def __init__(self, existing_id: str) -> None:
        self.existing_id = existing_id
        super().__init__(f"identical file already uploaded (doc {existing_id})")


def _original_key(file_id: str) -> str:
    return f"original/{file_id}.bin"


def _is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def _subject_context(audit: Audit) -> CredentialContext:
    """Audit subject data usable as password-derivation inputs."""
    return CredentialContext(name=audit.subject_name, dob=audit.subject_dob)


async def upload_document(
    session: Session,
    *,
    audit_id: str,
    filename: str,
    file_obj: BinaryIO,
    bank: Bank = Bank.UNKNOWN,
    doc_kind: DocKind = DocKind.UNKNOWN,
    password: str | None = None,
    save_credential: bool = False,
) -> AuditDocument:
    audit = session.get(Audit, audit_id)
    if audit is None:
        raise AuditNotFound(audit_id)

    hashed = hash_stream(file_obj)  # streamed sha256; dedupe on ORIGINAL bytes
    file_id = hashed.sha256

    existing = session.exec(
        select(AuditDocument).where(
            AuditDocument.audit_id == audit_id, AuditDocument.file_id == file_id
        )
    ).first()
    if existing is not None:
        raise DuplicateDocument(existing.id)

    store = get_store()
    store.save(_original_key(file_id), hashed.data)

    doc = AuditDocument(
        audit_id=audit_id,
        file_id=file_id,
        filename=filename,
        bank=bank.value,
        doc_kind=doc_kind.value,
    )

    if not _is_pdf(hashed.data):
        # Non-PDF (CSV/XLSX) lands in Phase 2's tabular path; store + park.
        doc.status = DocStatus.PENDING.value
        session.add(doc)
        session.commit()
        session.refresh(doc)
        return doc

    working = _gate_pdf(session, doc, hashed.data, audit, bank, password)
    if working is None:
        # locked — persisted inside _gate_pdf
        return doc

    _finalize_and_dispatch(session, doc, working)

    if save_credential and password:
        _maybe_save_credential(session, audit_id, bank, password)

    await get_pool().submit(lambda: run_extraction(doc.id))
    session.refresh(doc)
    return doc


def _gate_pdf(
    session: Session,
    doc: AuditDocument,
    data: bytes,
    audit: Audit,
    bank: Bank,
    typed_password: str | None,
) -> bytes | None:
    """Detect + unlock. Returns unlocked bytes, or None if it stays LOCKED."""
    doc.is_encrypted = is_encrypted(data)
    if not doc.is_encrypted:
        doc.password_status = PasswordStatus.NOT_REQUIRED.value
        return data

    candidates = cred_service.resolve_candidates(
        session,
        audit.id,
        bank,
        typed_password=typed_password,
        extra_context=_subject_context(audit),
    )
    try:
        res = unlock_pdf(data, candidates)
    except PdfPasswordRequired:
        doc.status = DocStatus.LOCKED.value
        doc.password_status = PasswordStatus.LOCKED.value
        session.add(doc)
        session.commit()
        session.refresh(doc)
        return None

    doc.password_status = PasswordStatus.UNLOCKED.value
    doc.unlocked_with_saved_credential = bool(
        res.password_used and res.password_used != typed_password
    )
    return res.data


def _finalize_and_dispatch(session: Session, doc: AuditDocument, working: bytes) -> None:
    store = get_store()
    store.save(work_key(doc.id), working)
    doc.page_count = PypdfPageExtractor().page_count(working)
    doc.pages_total = doc.page_count
    doc.pages_extracted = 0
    doc.status = DocStatus.PROCESSING.value
    session.add(doc)
    session.commit()
    session.refresh(doc)


def _maybe_save_credential(
    session: Session, audit_id: str, bank: Bank, password: str
) -> None:
    try:
        cred_service.save_bank_credential(
            session, scope_id=audit_id, bank=bank, literal=password
        )
    except cred_service.CredentialStorageDisabled:
        pass  # global switch off — silently skip saving


async def unlock_document(
    session: Session,
    *,
    audit_id: str,
    doc_id: str,
    password: str,
    save_credential: bool = False,
) -> AuditDocument:
    """Provide a password for a LOCKED doc; unlock + dispatch extraction."""
    doc = session.get(AuditDocument, doc_id)
    if doc is None or doc.audit_id != audit_id:
        raise AuditNotFound(doc_id)
    if doc.password_status != PasswordStatus.LOCKED.value:
        return doc  # already unlocked / not required — no-op

    audit = session.get(Audit, audit_id)
    data = get_store().load(_original_key(doc.file_id))
    bank = Bank(doc.bank)
    candidates = cred_service.resolve_candidates(
        session,
        audit_id,
        bank,
        typed_password=password,
        extra_context=_subject_context(audit) if audit else None,
    )
    res = unlock_pdf(data, candidates)  # raises PdfPasswordRequired if still wrong

    doc.password_status = PasswordStatus.UNLOCKED.value
    doc.unlocked_with_saved_credential = bool(
        res.password_used and res.password_used != password
    )
    _finalize_and_dispatch(session, doc, res.data)

    if save_credential:
        _maybe_save_credential(session, audit_id, bank, password)

    await get_pool().submit(lambda: run_extraction(doc.id))
    session.refresh(doc)
    return doc


def list_documents(session: Session, audit_id: str) -> list[AuditDocument]:
    stmt = (
        select(AuditDocument)
        .where(AuditDocument.audit_id == audit_id)
        .order_by(AuditDocument.created_at.asc())
    )
    return list(session.exec(stmt))


def get_document(session: Session, audit_id: str, doc_id: str) -> AuditDocument | None:
    doc = session.get(AuditDocument, doc_id)
    if doc is None or doc.audit_id != audit_id:
        return None
    return doc


def touch(session: Session, doc: AuditDocument) -> None:
    doc.updated_at = datetime.now(UTC)
    session.add(doc)
    session.commit()
