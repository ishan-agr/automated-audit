"""End-to-end ingest API tests: create audit → upload (plain / encrypted /
locked→unlock) → paged extraction with progress. Jobs run inline (see conftest)
so state is final by the time we GET it."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import make_encrypted_pdf, make_plain_pdf

client = TestClient(app)


def _new_audit(name: str = "Ishan Agrawal", dob: str | None = "2004-08-10") -> str:
    body: dict = {"subject_name": name}
    if dob:
        body["subject_dob"] = dob
    r = client.post("/api/v1/audits", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload(audit_id: str, data: bytes, **form) -> dict:
    files = {"file": ("stmt.pdf", data, "application/pdf")}
    r = client.post(f"/api/v1/audits/{audit_id}/documents", files=files, data=form)
    return r


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_audit_requires_name():
    assert client.post("/api/v1/audits", json={}).status_code == 422


def test_plain_pdf_extracts_all_pages():
    aid = _new_audit()
    r = _upload(aid, make_plain_pdf(pages=3))
    assert r.status_code == 202, r.text
    doc_id = r.json()["id"]

    got = client.get(f"/api/v1/audits/{aid}/documents/{doc_id}").json()
    assert got["is_encrypted"] is False
    assert got["password_status"] == "NOT_REQUIRED"
    assert got["status"] == "EXTRACTED"
    assert got["pages_total"] == 3
    assert got["pages_extracted"] == 3


def test_encrypted_pdf_auto_unlocks_from_bank_format():
    """Headline: HDFC-locked PDF, password derived from the audit's own name+DOB
    (ISHA + 1008), no password typed."""
    aid = _new_audit(name="Ishan Agrawal", dob="2004-08-10")
    enc = make_encrypted_pdf("ISHA1008")  # HDFC: FIRST4_UPPER(name)+DDMM(dob)
    r = _upload(aid, enc, bank="HDFC")
    assert r.status_code == 202, r.text
    doc_id = r.json()["id"]

    got = client.get(f"/api/v1/audits/{aid}/documents/{doc_id}").json()
    assert got["is_encrypted"] is True
    assert got["password_status"] == "UNLOCKED"
    assert got["unlocked_with_saved_credential"] is True  # derived, not typed
    assert got["status"] == "EXTRACTED"
    assert got["pages_extracted"] == got["pages_total"] == 1


def test_locked_then_unlock_endpoint():
    """No derivable password → LOCKED; unlock endpoint with the literal opens it."""
    aid = _new_audit(name="Zzz", dob=None)  # can't derive
    enc = make_encrypted_pdf("SBI-SECRET-99")
    r = _upload(aid, enc, bank="SBI")
    assert r.status_code == 202
    doc = r.json()
    assert doc["status"] == "LOCKED"
    assert doc["password_status"] == "LOCKED"
    doc_id = doc["id"]

    # wrong password → 422, still locked
    bad = client.post(
        f"/api/v1/audits/{aid}/documents/{doc_id}/unlock", json={"password": "nope"}
    )
    assert bad.status_code == 422

    # correct password → unlocked + extracted
    ok = client.post(
        f"/api/v1/audits/{aid}/documents/{doc_id}/unlock",
        json={"password": "SBI-SECRET-99"},
    )
    assert ok.status_code == 200, ok.text
    got = client.get(f"/api/v1/audits/{aid}/documents/{doc_id}").json()
    assert got["password_status"] == "UNLOCKED"
    assert got["status"] == "EXTRACTED"


def test_saved_credential_reused_for_second_statement():
    """Save the password on first unlock; a second locked file from the same bank
    unlocks automatically."""
    aid = _new_audit(name="Zzz", dob=None)
    first = make_encrypted_pdf("AXIS-PW-2026", pages=1)
    r1 = _upload(aid, first, bank="AXIS")
    d1 = r1.json()["id"]
    client.post(
        f"/api/v1/audits/{aid}/documents/{d1}/unlock",
        json={"password": "AXIS-PW-2026", "save_credential": True},
    )

    # different bytes (2 pages), same bank + password, no password supplied now.
    second = make_encrypted_pdf("AXIS-PW-2026", pages=2)
    r2 = _upload(aid, second, bank="AXIS")
    got = client.get(f"/api/v1/audits/{aid}/documents/{r2.json()['id']}").json()
    assert got["password_status"] == "UNLOCKED"
    assert got["status"] == "EXTRACTED"
    assert got["pages_total"] == 2


def test_duplicate_upload_rejected():
    aid = _new_audit()
    data = make_plain_pdf(1)
    assert _upload(aid, data).status_code == 202
    assert _upload(aid, data).status_code == 409  # identical bytes


def test_multiple_docs_multiple_passwords():
    aid = _new_audit(name="Zzz", dob=None)
    for pw in ("PW-hdfc-1", "PW-icici-2", "PW-axis-3"):
        enc = make_encrypted_pdf(pw)
        doc_id = _upload(aid, enc, bank="UNKNOWN").json()["id"]
        client.post(
            f"/api/v1/audits/{aid}/documents/{doc_id}/unlock", json={"password": pw}
        )
    docs = client.get(f"/api/v1/audits/{aid}/documents").json()
    assert len(docs) == 3
    assert all(d["status"] == "EXTRACTED" for d in docs)


def test_range_update_and_validation():
    aid = _new_audit()
    ok = client.patch(
        f"/api/v1/audits/{aid}/range",
        json={"range_from": "2026-04-01", "range_to": "2026-08-02"},
    )
    assert ok.status_code == 200
    assert ok.json()["range_to"] == "2026-08-02"
    bad = client.patch(
        f"/api/v1/audits/{aid}/range",
        json={"range_from": "2026-08-02", "range_to": "2026-04-01"},
    )
    assert bad.status_code == 422
