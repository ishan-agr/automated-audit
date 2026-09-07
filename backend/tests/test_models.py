"""Smoke tests: models import & instantiate, audit id format."""

from __future__ import annotations

from app.audit.ids import is_audit_id, new_audit_id
from app.audit.models import Audit, AuditStatus
from app.credentials.models import BankCredential, CredentialScope
from app.documents.models import AuditDocument, DocStatus, PasswordStatus


def test_audit_id_shape():
    aid = new_audit_id()
    assert aid.startswith("AUD-")
    assert is_audit_id(aid)
    assert not is_audit_id("AUD-lowercase")  # tail must be upper/alnum
    assert not is_audit_id("nope")


def test_audit_defaults():
    a = Audit(subject_name="Ishan Agrawal")
    assert a.id.startswith("AUD-")
    assert a.status == AuditStatus.DRAFT


def test_document_password_defaults():
    d = AuditDocument(audit_id="AUD-ABC123", file_id="f1", filename="axis.pdf")
    assert d.is_encrypted is False
    assert d.password_status == PasswordStatus.NOT_REQUIRED.value
    assert d.status == DocStatus.PENDING.value
    assert d.unlocked_with_saved_credential is False


def test_bank_credential_holds_only_ciphertext():
    c = BankCredential(
        scope=CredentialScope.AUDIT.value,
        scope_id="AUD-ABC123",
        bank="HDFC",
        secret_ciphertext="gAAAAA...",
    )
    assert c.scope == "AUDIT"
    assert c.secret_ciphertext  # plaintext never stored on the model
    assert c.context_ciphertext is None
