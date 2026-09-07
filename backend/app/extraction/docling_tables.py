"""Docling-backed table extractor (the real engine, per the reuse decision).

Converts a PDF (in memory) with Docling's layout + TableFormer models into
normalized `PageTable` grids + the document markdown. Heavy: the converter loads
models once (lazy, cached on the instance). Not exercised by the fast test suite —
covered by a manual smoke on the reference PDF.
"""

from __future__ import annotations

import io

from app.extraction.tables import PageTable


class DoclingTableExtractor:
    def __init__(self) -> None:
        self._converter = None  # lazy: model load is expensive

    def _get_converter(self):
        if self._converter is None:
            from docling.document_converter import DocumentConverter

            self._converter = DocumentConverter()
        return self._converter

    def extract(self, data: bytes) -> tuple[list[PageTable], str]:
        from docling.datamodel.base_models import DocumentStream

        source = DocumentStream(name="statement.pdf", stream=io.BytesIO(data))
        result = self._get_converter().convert(source)
        doc = result.document

        tables: list[PageTable] = []
        for t in doc.tables:
            page = t.prov[0].page_no if t.prov else 0
            df = t.export_to_dataframe()
            rows = [[str(c) for c in df.columns]]
            rows.extend([str(c) for c in row] for row in df.values.tolist())
            tables.append(PageTable(page_num=page, rows=rows))

        return tables, doc.export_to_markdown()
