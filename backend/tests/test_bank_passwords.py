"""Tests for bank password-format derivation (the 'stored against the bank' path)."""

from __future__ import annotations

from datetime import date

from app.bank_profiles.passwords import (
    Bank,
    CredentialContext,
    candidates_for_bank,
    hints_for_bank,
)


def test_hdfc_derives_name4_ddmm_and_ddmmyy():
    ctx = CredentialContext(name="Ishan Agrawal", dob=date(2004, 8, 10))
    cands = candidates_for_bank(Bank.HDFC, ctx)
    assert cands == ["ISHA1008", "ISHA100804"]  # DDMM then DDMMYY


def test_icici_offers_upper_and_lower_variants():
    ctx = CredentialContext(name="John Doe", dob=date(1990, 5, 22))
    cands = candidates_for_bank(Bank.ICICI, ctx)
    assert "JOHN2205" in cands
    assert "john2205" in cands


def test_name_drops_spaces_and_initials():
    # "A B Kumar" -> letters only -> "ABKu" first4.
    ctx = CredentialContext(name="A B Kumar", dob=date(2000, 1, 2))
    cands = candidates_for_bank(Bank.HDFC, ctx)
    assert cands[0] == "ABKU0201"


def test_missing_dob_yields_no_candidates():
    ctx = CredentialContext(name="Ishan Agrawal")  # no dob
    assert candidates_for_bank(Bank.HDFC, ctx) == []


def test_sbi_has_no_derivable_format():
    ctx = CredentialContext(name="Ishan Agrawal", dob=date(2004, 8, 10))
    assert candidates_for_bank(Bank.SBI, ctx) == []
    assert hints_for_bank(Bank.SBI) == []


def test_hints_are_human_readable():
    hints = hints_for_bank(Bank.HDFC)
    assert hints
    assert "date of birth" in hints[0]["description"].lower()
