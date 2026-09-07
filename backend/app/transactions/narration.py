"""Deterministic narration → structured identifiers parser.

Indian bank/UPI narration is highly structured, so a rules parser resolves the
vast majority for free (the SLM toggle, default off, only handles the messy tail).

Grammar observed in the Axis reference statement:
  UPI:  UPI / <P2M|P2A> / <ref> / <counterparty name> / <mode> / <bank>
  NEFT: NEFT / <UTR> / <counterparty name> / <bank> /
  (IMPS/RTGS follow the NEFT shape.)

Output carries the identifier enum map the audit groups by (NAME / UPI_ID /
REF_ID / COUNTERPARTY_BANK / CHANNEL) plus a confidence; low confidence flags a
row for review (or the SLM later).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Channel(str, Enum):
    UPI = "UPI"
    NEFT = "NEFT"
    IMPS = "IMPS"
    RTGS = "RTGS"
    POS = "POS"
    ATM = "ATM"
    CHEQUE = "CHEQUE"
    ACH = "ACH"
    CHARGE = "CHARGE"
    INTEREST = "INTEREST"
    OTHER = "OTHER"


# Tokens that appear in the UPI "mode" slot, never a real counterparty bank.
_MODE_TOKENS = {"UPI", "UPIINT", "VERIFI", "SENT B", "P2M", "P2A", "P2P", "UPIINT."}


@dataclass
class ParsedNarration:
    channel: str
    txn_subtype: str | None
    ref_id: str | None
    counterparty_name: str | None
    counterparty_bank: str | None
    counterparty_vpa: str | None
    identifiers: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def _build_ids(
    channel: str,
    name: str | None,
    vpa: str | None,
    ref: str | None,
    bank: str | None,
) -> dict[str, str]:
    ids: dict[str, str] = {"CHANNEL": channel}
    if name:
        ids["NAME"] = name
    if vpa:
        ids["UPI_ID"] = vpa
    if ref:
        ids["REF_ID"] = ref
    if bank:
        ids["COUNTERPARTY_BANK"] = bank
    return ids


_CHANNEL_MARKER = re.compile(r"(UPI|NEFT|IMPS|RTGS)/", re.IGNORECASE)


def parse_narration(raw: str) -> ParsedNarration:
    text = _clean(raw or "")
    if not text:
        return ParsedNarration(Channel.OTHER.value, None, None, None, None, None, {}, 0.0)

    # Trim leading wrap noise before a channel marker, e.g. "b/ UPI/..." → "UPI/...".
    m = _CHANNEL_MARKER.search(text)
    if m and m.start() > 0 and not text.upper().startswith(("UPI/", "NEFT/", "IMPS/", "RTGS/")):
        text = text[m.start() :]

    parts = [p.strip() for p in text.split("/")]
    head = parts[0].upper()

    if head == "UPI":
        return _parse_upi(parts)
    if head in ("NEFT", "IMPS", "RTGS"):
        return _parse_bank_transfer(parts, head)

    return _parse_keyword(text)


def _parse_upi(parts: list[str]) -> ParsedNarration:
    subtype = (
        parts[1].upper()
        if len(parts) > 1 and parts[1].upper() in {"P2M", "P2A", "P2P"}
        else None
    )
    ref = parts[2] if len(parts) > 2 and parts[2] else None
    name = parts[3] if len(parts) > 3 and parts[3] else None
    vpa = next((p for p in parts if "@" in p), None)

    # Bank = last non-empty token that isn't a mode marker.
    bank: str | None = None
    for p in reversed(parts[4:]):
        if p and p.upper() not in _MODE_TOKENS:
            bank = p
            break

    conf = 0.5
    if ref and name:
        conf = 0.9
    if subtype:
        conf += 0.04
    if bank:
        conf += 0.05
    conf = round(min(conf, 0.99), 2)

    return ParsedNarration(
        channel=Channel.UPI.value,
        txn_subtype=subtype,
        ref_id=ref,
        counterparty_name=name,
        counterparty_bank=bank,
        counterparty_vpa=vpa,
        identifiers=_build_ids(Channel.UPI.value, name, vpa, ref, bank),
        confidence=conf,
    )


def _parse_bank_transfer(parts: list[str], channel: str) -> ParsedNarration:
    ref = parts[1] if len(parts) > 1 and parts[1] else None
    name = parts[2] if len(parts) > 2 and parts[2] else None
    bank = next((p for p in reversed(parts[3:]) if p), None)

    conf = 0.85 if (ref and name) else 0.5
    if bank:
        conf += 0.05
    conf = round(min(conf, 0.98), 2)

    return ParsedNarration(
        channel=channel,
        txn_subtype=None,
        ref_id=ref,
        counterparty_name=name,
        counterparty_bank=bank,
        counterparty_vpa=None,
        identifiers=_build_ids(channel, name, None, ref, bank),
        confidence=conf,
    )


_KEYWORDS = [
    ("ATM", Channel.ATM),
    ("POS", Channel.POS),
    ("CHQ", Channel.CHEQUE),
    ("CHEQUE", Channel.CHEQUE),
    ("NACH", Channel.ACH),
    ("ACH", Channel.ACH),
    ("INT.", Channel.INTEREST),
    ("INTEREST", Channel.INTEREST),
    ("CHRG", Channel.CHARGE),
    ("CHARGE", Channel.CHARGE),
    ("GST", Channel.CHARGE),
]


def _parse_keyword(text: str) -> ParsedNarration:
    up = text.upper()
    for kw, channel in _KEYWORDS:
        if kw in up:
            return ParsedNarration(
                channel=channel.value,
                txn_subtype=None,
                ref_id=None,
                counterparty_name=None,
                counterparty_bank=None,
                counterparty_vpa=None,
                identifiers={"CHANNEL": channel.value},
                confidence=0.4,  # channel only — flagged for review / SLM
            )
    return ParsedNarration(
        channel=Channel.OTHER.value,
        txn_subtype=None,
        ref_id=None,
        counterparty_name=None,
        counterparty_bank=None,
        counterparty_vpa=None,
        identifiers={"CHANNEL": Channel.OTHER.value},
        confidence=0.2,
    )
