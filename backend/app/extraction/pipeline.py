"""Extraction pipeline: turn a document's unlocked working PDF into per-page
`ExtractedPage` rows, updating progress as it goes.

Runs in its own DB session (background-job safe). The working copy at
`work/<doc_id>.pdf` is always un-encrypted (the upload/unlock step guarantees it),
so the extractor never deals with passwords.
"""

from __future__ import annotations

from app.core.db import session_scope
from app.documents.models import AuditDocument, DocStatus, PasswordStatus
from app.extraction.base import Extractor
from app.extraction.page_store import ExtractedPage
from app.extraction.pypdf_extractor import PypdfPageExtractor
from app.files.storage import get_store


def work_key(doc_id: str) -> str:
    return f"work/{doc_id}.pdf"


async def run_extraction(doc_id: str, extractor: Extractor | None = None) -> None:
    """Extract every page of `doc_id`. Idempotent-ish: clears prior pages first."""
    extractor = extractor or PypdfPageExtractor()
    store = get_store()

    with session_scope() as session:
        doc = session.get(AuditDocument, doc_id)
        if doc is None:
            return
        if doc.password_status == PasswordStatus.LOCKED.value:
            return  # can't extract a still-locked doc
        doc.status = DocStatus.PROCESSING.value
        doc.pages_extracted = 0
        session.add(doc)
        session.commit()

    try:
        data = store.load(work_key(doc_id))
        total = extractor.page_count(data)
        with session_scope() as session:
            doc = session.get(AuditDocument, doc_id)
            assert doc is not None
            doc.page_count = total
            doc.pages_total = total
            session.add(doc)

        extracted = 0
        for page in extractor.iter_pages(data):
            with session_scope() as session:
                session.add(
                    ExtractedPage(
                        document_id=doc_id,
                        audit_id=_audit_id(session, doc_id),
                        page_num=page.page_num,
                        text=page.text,
                        char_count=len(page.text),
                    )
                )
                doc = session.get(AuditDocument, doc_id)
                assert doc is not None
                extracted += 1
                doc.pages_extracted = extracted
                session.add(doc)

        with session_scope() as session:
            doc = session.get(AuditDocument, doc_id)
            assert doc is not None
            doc.status = DocStatus.EXTRACTED.value
            session.add(doc)
    except Exception as exc:  # fail-soft, record the reason
        with session_scope() as session:
            doc = session.get(AuditDocument, doc_id)
            if doc is not None:
                doc.status = DocStatus.FAILED.value
                doc.error_message = f"{type(exc).__name__}: {exc}"[:2000]
                session.add(doc)
        raise


def _audit_id(session, doc_id: str) -> str:
    doc = session.get(AuditDocument, doc_id)
    return doc.audit_id if doc else ""
