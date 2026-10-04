"""CSV/XLSX tabular parser + CSV ingest→structure→export integration."""

from __future__ import annotations

import io

import pandas as pd
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.bank_profiles.tabular import parse_tabular
from app.core.db import get_engine
from app.main import app
from app.transactions import service

client = TestClient(app)

GPAY_CSV = (
    b"Date,Description,Amount,Type\n"
    b"2026-04-01,Paid to CRED Store,199.00,Debit\n"
    b"2026-04-02,Received from VICKY CHHATTANI,53.00,Credit\n"
)

BANK_CSV = (
    b"Account Statement\n"
    b"Account: 12345\n"
    b"\n"
    b"Txn Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\n"
    b"01/04/2026,UPI/P2M/123/Shop/UPI/AXIS BANK,710.00,,10256.18\n"
    b"03/04/2026,NEFT/xyz/Salary,,113900.00,124156.18\n"
)


def test_parse_gpay_like_type_column():
    p = parse_tabular(GPAY_CSV, "gpay.csv")
    assert len(p.txns) == 2
    debit = p.txns[0]
    assert debit.direction == "DEBIT"
    assert str(debit.amount) == "199.00"
    assert debit.tran_date.isoformat() == "2026-04-01"
    assert debit.narration == "Paid to CRED Store"
    assert p.txns[1].direction == "CREDIT"
    assert str(p.txns[1].amount) == "53.00"


def test_parse_bank_like_with_preamble_and_dr_cr_columns():
    p = parse_tabular(BANK_CSV, "bank.csv")
    assert len(p.txns) == 2
    w = p.txns[0]
    assert w.direction == "DEBIT"
    assert str(w.amount) == "710.00"
    assert w.tran_date.isoformat() == "2026-04-01"
    assert str(w.balance) == "10256.18"
    d = p.txns[1]
    assert d.direction == "CREDIT"
    assert str(d.amount) == "113900.00"


def test_parse_xlsx_round_trip():
    frame = pd.DataFrame(
        {
            "Date": ["2026-05-01"],
            "Description": ["Paid to Kirana"],
            "Amount": ["-250.00"],  # signed-amount fallback → DEBIT
        }
    )
    buf = io.BytesIO()
    frame.to_excel(buf, index=False)
    p = parse_tabular(buf.getvalue(), "export.xlsx")
    assert len(p.txns) == 1
    assert p.txns[0].direction == "DEBIT"
    assert str(p.txns[0].amount) == "250.00"


def _structure(doc_id: str) -> dict:
    with Session(get_engine()) as s:
        return service.structure_document(s, doc_id)


def test_csv_ingest_structure_and_export():
    aid = client.post(
        "/api/v1/audits", json={"subject_name": "Ishan Agrawal"}
    ).json()["id"]
    up = client.post(
        f"/api/v1/audits/{aid}/documents",
        files={"file": ("gpay.csv", GPAY_CSV, "text/csv")},
        data={"doc_kind": "UPI_EXPORT"},
    )
    assert up.status_code == 202
    doc = up.json()
    assert doc["status"] == "EXTRACTED"  # ready to structure, no OCR
    assert doc["password_status"] == "NOT_REQUIRED"

    out = _structure(doc["id"])
    assert out["transactions"] == 2

    txns = client.get(f"/api/v1/audits/{aid}/transactions").json()
    assert len(txns) == 2
    assert {t["direction"] for t in txns} == {"DEBIT", "CREDIT"}

    # export JSON = reconciliation + outputs
    rj = client.get(f"/api/v1/audits/{aid}/export?format=json")
    assert rj.status_code == 200
    assert "attachment" in rj.headers["content-disposition"]
    assert rj.json()["reconciliation"]["txn_count"] == 2

    # export CSV = flat transactions
    rc = client.get(f"/api/v1/audits/{aid}/export?format=csv")
    assert rc.status_code == 200
    assert rc.headers["content-type"].startswith("text/csv")
    body = rc.text
    assert "CRED Store" in body
    assert "VICKY CHHATTANI" in body
