"""ExtractedPage — per-page extracted text for a document (multi-page state).

Mirrors the KB engine's `kb_document_pages` idea: one row per page, so progress is
countable (`pages_extracted` = row count) and resume/parse can work page-by-page.
Phase 2's `parse_transactions` reads these rows.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


class ExtractedPage(SQLModel, table=True):
    __tablename__ = "extracted_pages"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    document_id: str = Field(index=True)
    audit_id: str = Field(index=True)
    page_num: int
    text: str = Field(default="")
    char_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
