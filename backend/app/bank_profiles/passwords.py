"""Bank password-format registry.

Different banks lock statement PDFs with different, *derivable* password formats
(e.g. "first 4 letters of the name in CAPS + DDMM of DOB"). This module models
those formats as data so we can:

  1. show the user a human hint per bank ("what does this bank use?"),
  2. derive candidate passwords from personal fields they provide once, and
  3. try those candidates automatically when unlocking that bank's PDFs.

Design notes
------------
* This is **best-effort convenience**, not authority. Real formats vary by
  product, vintage, and channel, and some banks (e.g. SBI e-statements) use a
  *user-chosen* password that is not derivable at all. So every derivation is
  offered as a *candidate* to try; the always-reliable path is the user entering
  or saving the literal password (see `BankCredential`). Formats are labelled
  ``verify=True`` when they are common-but-not-guaranteed.
* A bank may have several known variants → we return an ordered candidate list.
* Nothing here stores secrets; it only *derives* candidate strings in memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Bank(str, Enum):
    AXIS = "AXIS"
    HDFC = "HDFC"
    ICICI = "ICICI"
    SBI = "SBI"
    KOTAK = "KOTAK"
    UNKNOWN = "UNKNOWN"


class Field(str, Enum):
    """Personal fields a password may be derived from."""

    NAME = "NAME"
    DOB = "DOB"
    PAN = "PAN"
    ACCOUNT_NO = "ACCOUNT_NO"
    CUSTOMER_ID = "CUSTOMER_ID"
    MOBILE = "MOBILE"


class Transform(str, Enum):
    FIRST4_UPPER = "FIRST4_UPPER"
    FIRST4_LOWER = "FIRST4_LOWER"
    FIRST4 = "FIRST4"  # preserve case
    UPPER = "UPPER"
    LOWER = "LOWER"
    AS_IS = "AS_IS"
    DDMM = "DDMM"  # from a date
    DDMMYY = "DDMMYY"
    DDMMYYYY = "DDMMYYYY"
    YYYY = "YYYY"
    LAST4 = "LAST4"  # last 4 chars/digits (account/mobile)


@dataclass(frozen=True)
class Segment:
    """One piece of a password: a literal, or a transformed personal field."""

    field: Field | None = None
    transform: Transform = Transform.AS_IS
    literal: str | None = None


@dataclass(frozen=True)
class PasswordFormat:
    """An ordered list of segments that concatenate into a candidate password."""

    key: str
    description: str  # human hint for the UI
    segments: tuple[Segment, ...]
    verify: bool = True  # common-but-not-guaranteed → present as a hint

    def required_fields(self) -> set[Field]:
        return {s.field for s in self.segments if s.field is not None}


@dataclass
class CredentialContext:
    """Personal inputs a user may provide once to derive statement passwords.

    All optional; a format is skipped if its required fields are missing. These
    are sensitive — when persisted they live inside `BankCredential`, encrypted.
    """

    name: str | None = None
    dob: date | None = None
    pan: str | None = None
    account_no: str | None = None
    customer_id: str | None = None
    mobile: str | None = None

    def get(self, f: Field) -> str | date | None:
        return {
            Field.NAME: self.name,
            Field.DOB: self.dob,
            Field.PAN: self.pan,
            Field.ACCOUNT_NO: self.account_no,
            Field.CUSTOMER_ID: self.customer_id,
            Field.MOBILE: self.mobile,
        }[f]


def _alpha(s: str) -> str:
    """Keep only letters — names in passwords usually drop spaces/initials."""
    return "".join(ch for ch in s if ch.isalpha())


def _digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def _apply(value: str | date, t: Transform) -> str | None:
    if isinstance(value, date):
        if t == Transform.DDMM:
            return f"{value.day:02d}{value.month:02d}"
        if t == Transform.DDMMYY:
            return f"{value.day:02d}{value.month:02d}{value.year % 100:02d}"
        if t == Transform.DDMMYYYY:
            return f"{value.day:02d}{value.month:02d}{value.year:04d}"
        if t == Transform.YYYY:
            return f"{value.year:04d}"
        return None  # a date with a text transform is undefined
    s = value
    if t == Transform.FIRST4_UPPER:
        return _alpha(s)[:4].upper()
    if t == Transform.FIRST4_LOWER:
        return _alpha(s)[:4].lower()
    if t == Transform.FIRST4:
        return _alpha(s)[:4]
    if t == Transform.UPPER:
        return s.upper()
    if t == Transform.LOWER:
        return s.lower()
    if t == Transform.LAST4:
        return _digits(s)[-4:] if _digits(s) else s[-4:]
    if t == Transform.AS_IS:
        return s
    return None


def derive(fmt: PasswordFormat, ctx: CredentialContext) -> str | None:
    """Derive the candidate password for one format, or None if inputs missing."""
    out: list[str] = []
    for seg in fmt.segments:
        if seg.literal is not None:
            out.append(seg.literal)
            continue
        assert seg.field is not None
        raw = ctx.get(seg.field)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return None  # required field missing → this format can't be derived
        piece = _apply(raw, seg.transform)
        if piece is None or piece == "":
            return None
        out.append(piece)
    return "".join(out)


# ---------------------------------------------------------------------------
# Known formats. COMMON, NOT AUTHORITATIVE — every one is `verify=True`. Order
# within a bank = priority (most common first).
# ---------------------------------------------------------------------------

_NAME4U_DDMM = PasswordFormat(
    key="name4upper_ddmm",
    description="First 4 letters of name (CAPS) + DDMM of date of birth",
    segments=(
        Segment(Field.NAME, Transform.FIRST4_UPPER),
        Segment(Field.DOB, Transform.DDMM),
    ),
)
_NAME4U_DDMMYY = PasswordFormat(
    key="name4upper_ddmmyy",
    description="First 4 letters of name (CAPS) + DDMMYY of date of birth",
    segments=(
        Segment(Field.NAME, Transform.FIRST4_UPPER),
        Segment(Field.DOB, Transform.DDMMYY),
    ),
)
_NAME4L_DDMM = PasswordFormat(
    key="name4lower_ddmm",
    description="First 4 letters of name (lowercase) + DDMM of date of birth",
    segments=(
        Segment(Field.NAME, Transform.FIRST4_LOWER),
        Segment(Field.DOB, Transform.DDMM),
    ),
)
_PAN_ONLY = PasswordFormat(
    key="pan_lower",
    description="PAN in lowercase",
    segments=(Segment(Field.PAN, Transform.LOWER),),
)

KNOWN_FORMATS: dict[Bank, list[PasswordFormat]] = {
    Bank.HDFC: [_NAME4U_DDMM, _NAME4U_DDMMYY],
    Bank.ICICI: [_NAME4U_DDMM, _NAME4L_DDMM],
    Bank.AXIS: [_NAME4U_DDMM, _NAME4U_DDMMYY],
    Bank.KOTAK: [_NAME4U_DDMM],
    # SBI e-statements use a user-chosen password → not derivable. Provide no
    # format; the user must supply/save the literal password.
    Bank.SBI: [],
    Bank.UNKNOWN: [],
}


def candidates_for_bank(bank: Bank, ctx: CredentialContext) -> list[str]:
    """Ordered, de-duplicated candidate passwords for a bank given personal inputs."""
    seen: set[str] = set()
    out: list[str] = []
    for fmt in KNOWN_FORMATS.get(bank, []):
        pw = derive(fmt, ctx)
        if pw and pw not in seen:
            seen.add(pw)
            out.append(pw)
    return out


def hints_for_bank(bank: Bank) -> list[dict[str, str]]:
    """UI hints: what password formats this bank commonly uses."""
    return [
        {"key": f.key, "description": f.description, "verify": str(f.verify).lower()}
        for f in KNOWN_FORMATS.get(bank, [])
    ]
