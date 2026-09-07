"""End-to-end smoke on the real Axis PDF: upload → Docling structure → generate.
Run with temp env, e.g.:
  AUDIT_INLINE_JOBS=1 AUDIT_DATA_DIR=./smoke_data AUDIT_DATABASE_URL=sqlite:///./smoke.db \
  AUDIT_SECRET_KEY=... .venv/Scripts/python.exe scripts/smoke_phase2.py
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.db import get_engine
from app.main import app
from app.transactions import service

PDF = r"D:/automated-audit/automated-audit/AcctStatement_XXX7229_02082026.pdf"
c = TestClient(app)


def main() -> None:
    aid = c.post(
        "/api/v1/audits",
        json={"subject_name": "Ishan Agrawal", "subject_dob": "2004-08-10"},
    ).json()["id"]
    with open(PDF, "rb") as f:
        r = c.post(
            f"/api/v1/audits/{aid}/documents",
            files={"file": ("axis.pdf", f.read(), "application/pdf")},
            data={"bank": "AXIS", "doc_kind": "BANK_STATEMENT"},
        )
    doc_id = r.json()["id"]
    print("audit", aid, "| upload", r.status_code, "| pages", r.json().get("pages_total"))

    with Session(get_engine()) as s:
        out = service.structure_document(s, doc_id)  # REAL Docling
    print("structured:", out)

    txns = c.get(f"/api/v1/audits/{aid}/transactions").json()
    print("txn count:", len(txns))
    for t in txns[:4]:
        print("  ", t["tran_date"], t["direction"], t["amount"], t["channel"], "|", t["counterparty_name"])

    c.patch(
        f"/api/v1/audits/{aid}/range",
        json={"range_from": "2026-04-01", "range_to": "2026-08-02"},
    )
    gen = c.post(f"/api/v1/audits/{aid}/generate").json()
    print("=== reconciliation ===")
    print(json.dumps(gen["reconciliation"], indent=2))


if __name__ == "__main__":
    main()
