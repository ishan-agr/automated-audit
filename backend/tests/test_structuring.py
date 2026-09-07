"""Phase 2→2.5→3 integration: structure (fake extractor) → transactions →
generate (reconcile + report DAG). Real Docling is covered by a manual smoke."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.db import get_engine
from app.extraction.tables import PageTable
from app.main import app
from app.transactions import service
from tests.conftest import make_plain_pdf

client = TestClient(app)

HEADER_TEXT = (
    "Statement of Axis Account No: 924010023017229 for the period "
    "(From: 01-04-2026  To: 02-08-2026)"
)

# Chained balances so reconciliation continuity holds:
# opening 10966.18 → debit 710 → 10256.18 → credit 113900 → 124156.18 (closing).
TABLES = [
    PageTable(
        page_num=1,
        rows=[
            ["Tran Date Chq No", "Particulars", "Debit", "Credit", "Balance", "Init. Br"],
            ["", "OPENING BALANCE", "", "", "10966.18", ""],
            ["01-04-2026", "UPI/P2M/645702960479/Google India Digital/UPI/AXIS BANK", "710.00", "", "10256.18", "5016"],
            ["03-04-2026", "NEFT/0811OP6172079607/MAGURE TECH INDIA PRIVATE LI/DBS BANK INDIA LIMIT/", "", "113900.00", "124156.18", "248"],
            ["", "TRANSACTION TOTAL", "710.00", "113900.00", "", ""],
            ["", "CLOSING BALANCE", "", "", "124156.18", ""],
        ],
    )
]


class FakeExtractor:
    def extract(self, data: bytes):
        return TABLES, HEADER_TEXT


def _audit_with_doc() -> tuple[str, str]:
    aid = client.post(
        "/api/v1/audits", json={"subject_name": "Ishan Agrawal"}
    ).json()["id"]
    r = client.post(
        f"/api/v1/audits/{aid}/documents",
        files={"file": ("axis.pdf", make_plain_pdf(1), "application/pdf")},
        data={"bank": "AXIS", "doc_kind": "BANK_STATEMENT"},
    )
    return aid, r.json()["id"]


def _structure(doc_id: str) -> dict:
    with Session(get_engine()) as s:
        return service.structure_document(s, doc_id, table_extractor=FakeExtractor())


def test_structure_persists_transactions():
    aid, doc_id = _audit_with_doc()
    out = _structure(doc_id)
    assert out["transactions"] == 2
    assert out["account_no"] == "924010023017229"
    assert out["opening_balance"] == "10966.18"

    txns = client.get(f"/api/v1/audits/{aid}/transactions").json()
    assert len(txns) == 2
    google = txns[0]
    assert google["channel"] == "UPI"
    assert google["counterparty_name"] == "Google India Digital"
    assert google["direction"] == "DEBIT"
    assert google["source_account"] == "924010023017229"
    assert google["identifiers"]["REF_ID"] == "645702960479"


def test_generate_reconciliation_over_persisted():
    aid, doc_id = _audit_with_doc()
    _structure(doc_id)
    client.patch(
        f"/api/v1/audits/{aid}/range",
        json={"range_from": "2026-04-01", "range_to": "2026-08-02"},
    )
    gen = client.post(f"/api/v1/audits/{aid}/generate").json()
    recon = gen["reconciliation"]
    assert recon["total_debit"] == "710.00"
    assert recon["total_credit"] == "113900.00"
    assert recon["net"] == "113190.00"
    assert recon["accounts"][0]["account"] == "924010023017229"
    assert recon["accounts"][0]["continuity_ok"] is True


def test_generate_with_card_graph():
    aid, doc_id = _audit_with_doc()
    _structure(doc_id)
    graph = {
        "name": "Spend",
        "nodes": [
            {"id": "g", "kind": "TXN_GROUP", "config": {"selector": {"direction": "DEBIT"}}},
            {"id": "s", "kind": "AGGREGATE", "config": {"fn": "SUM"}},
            {"id": "o", "kind": "OUTPUT", "config": {"label": "Total spend", "format": "CURRENCY"}},
        ],
        "edges": [
            {"source": "g", "target": "s"},
            {"source": "s", "target": "o"},
        ],
    }
    assert client.put(f"/api/v1/audits/{aid}/report", json=graph).status_code == 200
    gen = client.post(f"/api/v1/audits/{aid}/generate").json()
    assert gen["outputs"][0]["label"] == "Total spend"
    assert gen["outputs"][0]["value"] == "710.00"


def test_put_report_rejects_cycle():
    aid, _ = _audit_with_doc()
    graph = {
        "nodes": [
            {"id": "a", "kind": "CONSTANT", "config": {"value": 1}},
            {"id": "b", "kind": "CONSTANT", "config": {"value": 2}},
        ],
        "edges": [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "a"},
        ],
    }
    assert client.put(f"/api/v1/audits/{aid}/report", json=graph).status_code == 422
