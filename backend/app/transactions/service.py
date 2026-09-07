"""Transaction structuring: Docling tables → deterministic parse → persist
`ExtractedTransaction` + `DocumentMeta`. Idempotent (clears prior rows for the doc).
The table extractor is injectable so the parse/persist path is unit-testable
without running Docling.
"""

from __future__ import annotations

from sqlmodel import Session, delete, select

from app.bank_profiles.axis import parse_axis_header, parse_axis_tables
from app.documents.models import AuditDocument, DocStatus
from app.extraction.pipeline import work_key
from app.extraction.tables import TableExtractor
from app.files.storage import get_store
from app.transactions.models import DocumentMeta, ExtractedTransaction, ParseSource
from app.transactions.narration import parse_narration


class DocumentNotFound(Exception):
    pass


def _default_extractor() -> TableExtractor:
    from app.extraction.docling_tables import DoclingTableExtractor

    return DoclingTableExtractor()


def structure_document(
    session: Session,
    doc_id: str,
    *,
    table_extractor: TableExtractor | None = None,
) -> dict:
    doc = session.get(AuditDocument, doc_id)
    if doc is None:
        raise DocumentNotFound(doc_id)
    extractor = table_extractor or _default_extractor()

    data = get_store().load(work_key(doc_id))
    tables, text = extractor.extract(data)

    parsed = parse_axis_tables(tables)
    header = parse_axis_header(text)
    account_no = header.get("account_no")

    # idempotent re-structure
    session.exec(delete(ExtractedTransaction).where(ExtractedTransaction.document_id == doc_id))

    for rt in parsed.txns:
        narr = parse_narration(rt.narration)
        session.add(
            ExtractedTransaction(
                audit_id=doc.audit_id,
                document_id=doc_id,
                page_num=rt.page_num,
                row_index=rt.row_index,
                tran_date=rt.tran_date,
                narration_raw=rt.narration,
                direction=rt.direction,
                amount=rt.amount,
                balance=rt.balance,
                channel=narr.channel,
                txn_subtype=narr.txn_subtype,
                ref_id=narr.ref_id,
                identifiers=narr.identifiers,
                counterparty_name=narr.counterparty_name,
                source_account=account_no,
                confidence=narr.confidence,
                parse_source=ParseSource.REGEX.value,
                raw_json={},
            )
        )

    kv = dict(header)
    if parsed.opening_balance is not None:
        kv["opening_balance"] = str(parsed.opening_balance)
    if parsed.closing_balance is not None:
        kv["closing_balance"] = str(parsed.closing_balance)
    if parsed.total_debit is not None:
        kv["total_debit"] = str(parsed.total_debit)
    if parsed.total_credit is not None:
        kv["total_credit"] = str(parsed.total_credit)

    existing = session.exec(
        select(DocumentMeta).where(DocumentMeta.document_id == doc_id)
    ).first()
    if existing:
        existing.kv = kv
        session.add(existing)
    else:
        session.add(DocumentMeta(document_id=doc_id, audit_id=doc.audit_id, kv=kv))

    doc.status = DocStatus.READY.value
    session.add(doc)
    session.commit()

    return {
        "document_id": doc_id,
        "transactions": len(parsed.txns),
        "account_no": account_no,
        "opening_balance": kv.get("opening_balance"),
        "closing_balance": kv.get("closing_balance"),
    }


def list_transactions(
    session: Session, audit_id: str, limit: int = 500, offset: int = 0
) -> list[ExtractedTransaction]:
    stmt = (
        select(ExtractedTransaction)
        .where(ExtractedTransaction.audit_id == audit_id)
        .order_by(ExtractedTransaction.tran_date, ExtractedTransaction.row_index)
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(stmt))
