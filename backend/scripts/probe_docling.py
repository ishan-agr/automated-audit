"""One-off probe: what does Docling extract from the Axis statement?
Run: .venv/Scripts/python.exe scripts/probe_docling.py
First run downloads layout + TableFormer models (slow, CPU)."""

from __future__ import annotations

from docling.document_converter import DocumentConverter

PDF = r"D:/automated-audit/automated-audit/AcctStatement_XXX7229_02082026.pdf"


def main() -> None:
    conv = DocumentConverter()
    res = conv.convert(PDF)
    doc = res.document
    print("=== TABLES:", len(doc.tables))
    for i, t in enumerate(doc.tables):
        page = None
        if t.prov:
            page = t.prov[0].page_no
        df = t.export_to_dataframe()
        print(f"--- table {i} page={page} shape={df.shape}")
        print("cols:", list(df.columns))
        print(df.head(6).to_string()[:1600])
    print("=== MARKDOWN (first 1500 chars) ===")
    print(doc.export_to_markdown()[:1500])


if __name__ == "__main__":
    main()
