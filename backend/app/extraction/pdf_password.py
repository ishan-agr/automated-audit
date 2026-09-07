"""Password-protected PDF handling — the first gate of the ingest pipeline.

Bank/UPI statement PDFs are frequently encrypted, and **different documents in
one audit carry different passwords** (each bank uses its own format). This module
sits at the head of extraction: it detects encryption and, given a set of
candidate passwords (typed by the user and/or derived from the bank's stored
credential), unlocks the file and returns an **un-encrypted byte stream** so the
rest of the pipeline (Docling / pdfium / TableFormer) never has to deal with
encryption.

Contract:
  * not encrypted           -> returned unchanged, `password_used=None`.
  * encrypted, a candidate works -> decrypted, re-serialised WITHOUT encryption.
  * encrypted, nothing works -> raise `PdfPasswordRequired` (caller asks the user).
  * malformed / not a PDF    -> raise `PdfDecryptError`.

The empty password `""` is always tried first: many "encrypted" statements only
set an *owner* password (permissions) with a blank *user* password and open fine.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError


class PdfPasswordError(Exception):
    """Base class for PDF password problems."""


class PdfPasswordRequired(PdfPasswordError):
    """Encrypted PDF that none of the supplied candidates could open."""

    def __init__(self, tried: int) -> None:
        self.tried = tried
        super().__init__(
            f"PDF is password-protected and none of the {tried} candidate "
            "password(s) worked."
        )


class PdfDecryptError(PdfPasswordError):
    """The bytes are not a readable PDF (corrupt / not a PDF)."""


@dataclass
class UnlockResult:
    data: bytes  # always un-encrypted, ready for the extractor
    was_encrypted: bool
    password_used: str | None  # None if it wasn't encrypted or opened blank
    tried: int  # how many candidates were attempted


def is_encrypted(data: bytes) -> bool:
    """True if the PDF is encrypted. Raises `PdfDecryptError` if not a PDF."""
    try:
        return bool(PdfReader(BytesIO(data)).is_encrypted)
    except PdfReadError as exc:
        raise PdfDecryptError(str(exc)) from exc


def _reserialize_unencrypted(reader: PdfReader) -> bytes:
    """Write a decrypted reader out as a fresh, un-encrypted PDF."""
    writer = PdfWriter()
    writer.append(reader)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def unlock_pdf(data: bytes, candidates: Sequence[str] | None = None) -> UnlockResult:
    """Return an un-encrypted copy of `data`, trying `candidates` if needed.

    `candidates` are tried in order; the empty password is always tried first.
    Duplicate candidates are collapsed so a caller can pass a loose list.
    """
    try:
        reader = PdfReader(BytesIO(data))
    except PdfReadError as exc:
        raise PdfDecryptError(str(exc)) from exc

    if not reader.is_encrypted:
        return UnlockResult(data=data, was_encrypted=False, password_used=None, tried=0)

    # "" first (owner-only locks), then de-duplicated caller candidates.
    ordered: list[str] = [""]
    for pw in candidates or []:
        if pw not in ordered:
            ordered.append(pw)

    tried = 0
    for pw in ordered:
        tried += 1
        try:
            result = reader.decrypt(pw)
        except (PdfReadError, NotImplementedError) as exc:
            # e.g. an unsupported encryption algorithm — surface clearly.
            raise PdfDecryptError(f"cannot decrypt PDF: {exc}") from exc
        # pypdf returns PasswordType (IntEnum): 0 = NOT_DECRYPTED, >0 = ok.
        if int(result) > 0:
            password_used = pw if pw != "" else None
            return UnlockResult(
                data=_reserialize_unencrypted(reader),
                was_encrypted=True,
                password_used=password_used,
                tried=tried,
            )

    raise PdfPasswordRequired(tried=tried)
