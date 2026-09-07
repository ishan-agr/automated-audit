"""Tests for the password-protected PDF unlock gate."""

from __future__ import annotations

import pytest

from app.extraction.pdf_password import (
    PdfDecryptError,
    PdfPasswordRequired,
    is_encrypted,
    unlock_pdf,
)


def test_plain_pdf_passes_through(plain_pdf: bytes):
    assert is_encrypted(plain_pdf) is False
    res = unlock_pdf(plain_pdf)
    assert res.was_encrypted is False
    assert res.password_used is None
    assert res.tried == 0
    assert res.data == plain_pdf  # unchanged


def test_detects_encryption(encrypted_pdf_factory):
    enc = encrypted_pdf_factory("ISHA1008")
    assert is_encrypted(enc) is True


def test_unlock_with_correct_password(encrypted_pdf_factory):
    enc = encrypted_pdf_factory("ISHA1008")
    res = unlock_pdf(enc, ["WRONG1", "ISHA1008", "WRONG2"])
    assert res.was_encrypted is True
    assert res.password_used == "ISHA1008"
    # Output must be an un-encrypted, readable PDF.
    assert is_encrypted(res.data) is False


def test_wrong_passwords_raise(encrypted_pdf_factory):
    enc = encrypted_pdf_factory("CORRECT99")
    with pytest.raises(PdfPasswordRequired) as ei:
        unlock_pdf(enc, ["nope", "still-nope"])
    # tried counts the empty-password attempt + the two candidates.
    assert ei.value.tried == 3


def test_owner_only_lock_opens_with_blank_password(encrypted_pdf_factory):
    # Encrypted with a blank user password (only owner/permissions set).
    enc = encrypted_pdf_factory("", owner_password="owner-secret")
    res = unlock_pdf(enc, [])  # no candidates needed; "" is tried first
    assert res.was_encrypted is True
    assert res.password_used is None  # opened blank
    assert is_encrypted(res.data) is False


def test_not_a_pdf_raises_decrypt_error():
    with pytest.raises(PdfDecryptError):
        is_encrypted(b"this is definitely not a pdf")


def test_multiple_docs_multiple_passwords(encrypted_pdf_factory):
    """The headline requirement: many PDFs, each with its own password."""
    docs = {
        "hdfc.pdf": ("ISHA1008", encrypted_pdf_factory("ISHA1008")),
        "icici.pdf": ("john2205", encrypted_pdf_factory("john2205")),
        "axis.pdf": ("VICK3112", encrypted_pdf_factory("VICK3112")),
    }
    for pw, data in docs.values():
        # Each doc unlocked independently with its own password.
        res = unlock_pdf(data, [pw])
        assert res.password_used == pw
        assert is_encrypted(res.data) is False
