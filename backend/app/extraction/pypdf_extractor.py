"""Baseline paged text extractor using pypdf's text layer.

Bank/UPI statements are digital-text PDFs, so the pdfium/pypdf text layer already
yields clean per-page text — enough to build and test the whole ingest→parse spine
locally without the heavy Docling stack. The Docling adapter (layout + TableFormer
+ router) will replace this for scanned/complex pages behind the same `Extractor`
protocol.
"""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO

from pypdf import PdfReader

from app.extraction.base import ExtractedPageData


class PypdfPageExtractor:
    def page_count(self, data: bytes) -> int:
        return len(PdfReader(BytesIO(data)).pages)

    def iter_pages(self, data: bytes) -> Iterator[ExtractedPageData]:
        reader = PdfReader(BytesIO(data))
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            yield ExtractedPageData(page_num=i, text=text)
