"""Narration parser tests using real strings from the Axis reference statement."""

from __future__ import annotations

from app.transactions.narration import Channel, parse_narration


def test_upi_p2m_merchant():
    p = parse_narration("UPI/P2M/645702960479/Google India Digital/UPI/AXIS BANK")
    assert p.channel == Channel.UPI.value
    assert p.txn_subtype == "P2M"
    assert p.ref_id == "645702960479"
    assert p.counterparty_name == "Google India Digital"
    assert p.counterparty_bank == "AXIS BANK"
    assert p.identifiers["NAME"] == "Google India Digital"
    assert p.identifiers["REF_ID"] == "645702960479"
    assert p.confidence >= 0.9


def test_upi_p2a_person():
    p = parse_narration("UPI/P2A/609293639186/SHARAD KUMAR DHANDE/UPI/ICICI Bank")
    assert p.txn_subtype == "P2A"
    assert p.counterparty_name == "SHARAD KUMAR DHANDE"
    assert p.counterparty_bank == "ICICI Bank"


def test_upi_mode_token_not_treated_as_bank():
    # ...kettoorg / UPIInt / AXIS BANK  → bank must skip the mode token 'UPIInt'
    p = parse_narration("UPI/P2M/609214912356/kettoorg/UPIInt/AXIS BANK")
    assert p.counterparty_name == "kettoorg"
    assert p.counterparty_bank == "AXIS BANK"


def test_neft_transfer():
    p = parse_narration(
        "NEFT/0811OP6172079607/MAGURE TECH INDIA PRIVATE LI/DBS BANK INDIA LIMIT/"
    )
    assert p.channel == Channel.NEFT.value
    assert p.ref_id == "0811OP6172079607"
    assert p.counterparty_name == "MAGURE TECH INDIA PRIVATE LI"
    assert p.counterparty_bank == "DBS BANK INDIA LIMIT"


def test_verifi_mode_variant():
    p = parse_narration("UPI/P2M/610280943984/Sukh Specialty Coffee/Verifi/YES BANK LIMITED YBS")
    assert p.counterparty_name == "Sukh Specialty Coffee"
    assert p.counterparty_bank == "YES BANK LIMITED YBS"


def test_unknown_low_confidence():
    p = parse_narration("SOME RANDOM NARRATION")
    assert p.channel == Channel.OTHER.value
    assert p.confidence < 0.5  # flagged for review / SLM


def test_empty():
    p = parse_narration("")
    assert p.channel == Channel.OTHER.value
    assert p.confidence == 0.0
