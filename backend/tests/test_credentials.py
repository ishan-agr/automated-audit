"""Tests for candidate assembly + encrypted-at-rest credential storage."""

from __future__ import annotations

from datetime import date

from app.bank_profiles.passwords import Bank, CredentialContext
from app.credentials.service import (
    build_candidates,
    context_from_ciphertext,
    context_to_ciphertext,
    literal_from_ciphertext,
    literal_to_ciphertext,
)


def test_candidate_priority_typed_then_saved_then_derived():
    ctx = CredentialContext(name="Ishan Agrawal", dob=date(2004, 8, 10))
    cands = build_candidates(
        Bank.HDFC,
        typed_password="typed-wins",
        saved_literal="saved-literal",
        context=ctx,
    )
    assert cands[0] == "typed-wins"
    assert cands[1] == "saved-literal"
    assert "ISHA1008" in cands[2:]  # derived come last


def test_candidates_dedupe_and_skip_empty():
    cands = build_candidates(
        Bank.HDFC, typed_password="", saved_literal="same", context=None
    )
    assert cands == ["same"]


def test_literal_ciphertext_round_trip():
    token = literal_to_ciphertext("ISHA1008")
    assert token != "ISHA1008"  # actually encrypted
    assert literal_from_ciphertext(token) == "ISHA1008"


def test_context_ciphertext_round_trip():
    ctx = CredentialContext(
        name="Ishan Agrawal",
        dob=date(2004, 8, 10),
        pan="ABCDE1234F",
        customer_id="965401934",
    )
    token = context_to_ciphertext(ctx)
    assert "Ishan" not in token  # no plaintext leakage
    back = context_from_ciphertext(token)
    assert back.name == "Ishan Agrawal"
    assert back.dob == date(2004, 8, 10)
    assert back.pan == "ABCDE1234F"
    assert back.customer_id == "965401934"
