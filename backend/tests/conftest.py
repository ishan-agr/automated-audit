"""Shared test fixtures — isolated env (temp DB + store, inline jobs, fixed key)
and an encrypted/plain PDF factory. Env is set BEFORE any app import so cached
settings pick it up.
"""

from __future__ import annotations

import os
import tempfile
from io import BytesIO

import pytest

_TMP = tempfile.mkdtemp(prefix="aa-test-")
os.environ.setdefault("AUDIT_SECRET_KEY", "sQ8m0Yy3n0m3aQm4d2m3v9nUqk1r5cX2pY8sT4wZ7dE=")
os.environ.setdefault("AUDIT_DATA_DIR", _TMP)
os.environ.setdefault("AUDIT_DATABASE_URL", f"sqlite:///{_TMP}/test.db")
os.environ.setdefault("AUDIT_INLINE_JOBS", "1")  # deterministic extraction in tests

from pypdf import PdfWriter


def make_plain_pdf(pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_encrypted_pdf(
    user_password: str, owner_password: str | None = None, pages: int = 1
) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    writer.encrypt(user_password=user_password, owner_password=owner_password)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def plain_pdf() -> bytes:
    return make_plain_pdf(1)


@pytest.fixture
def encrypted_pdf_factory():
    return make_encrypted_pdf
