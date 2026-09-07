"""Turn a bank + whatever the user gave us into an ordered list of candidate
passwords for `unlock_pdf`, and (opt-in) persist a bank credential encrypted.

Candidate priority (first match wins in `unlock_pdf`):
  1. the password typed for *this* upload (explicit, most specific),
  2. a literal password saved against this bank (opt-in convenience),
  3. passwords *derived* from the bank's known format(s) + saved personal inputs.

This is why "store the password against the bank" works: on the next statement
from that bank we already have (2) and/or the inputs for (3), so the user doesn't
retype anything.
"""

from __future__ import annotations

import json
from datetime import date

from sqlmodel import Session, select

from app.bank_profiles.passwords import (
    Bank,
    CredentialContext,
    candidates_for_bank,
)
from app.core.config import get_settings
from app.core.crypto import get_secret_box
from app.credentials.models import BankCredential, CredentialScope


def build_candidates(
    bank: Bank,
    *,
    typed_password: str | None = None,
    saved_literal: str | None = None,
    context: CredentialContext | None = None,
) -> list[str]:
    """Ordered, de-duplicated candidate passwords. Empty inputs are ignored."""
    ordered: list[str] = []

    def add(pw: str | None) -> None:
        if pw and pw not in ordered:
            ordered.append(pw)

    add(typed_password)
    add(saved_literal)
    for pw in candidates_for_bank(bank, context) if context else []:
        add(pw)
    return ordered


# --- opt-in encrypted persistence helpers ---------------------------------

def context_to_ciphertext(ctx: CredentialContext) -> str:
    payload = {
        "name": ctx.name,
        "dob": ctx.dob.isoformat() if ctx.dob else None,
        "pan": ctx.pan,
        "account_no": ctx.account_no,
        "customer_id": ctx.customer_id,
        "mobile": ctx.mobile,
    }
    return get_secret_box().encrypt(json.dumps(payload))


def context_from_ciphertext(token: str) -> CredentialContext:
    payload = json.loads(get_secret_box().decrypt(token))
    dob = payload.get("dob")
    return CredentialContext(
        name=payload.get("name"),
        dob=date.fromisoformat(dob) if dob else None,
        pan=payload.get("pan"),
        account_no=payload.get("account_no"),
        customer_id=payload.get("customer_id"),
        mobile=payload.get("mobile"),
    )


def literal_to_ciphertext(password: str) -> str:
    return get_secret_box().encrypt(password)


def literal_from_ciphertext(token: str) -> str:
    return get_secret_box().decrypt(token)


# --- DB-backed persistence + resolution (opt-in) --------------------------

class CredentialStorageDisabled(RuntimeError):
    """Raised when a save is attempted but storage is globally disabled."""


def get_saved_credential(
    session: Session, scope_id: str, bank: Bank
) -> BankCredential | None:
    """Most recent stored credential for (scope_id, bank), or None."""
    stmt = (
        select(BankCredential)
        .where(BankCredential.scope_id == scope_id, BankCredential.bank == bank.value)
        .order_by(BankCredential.created_at.desc())
    )
    return session.exec(stmt).first()


def save_bank_credential(
    session: Session,
    *,
    scope_id: str,
    bank: Bank,
    literal: str | None = None,
    context: CredentialContext | None = None,
    label: str | None = None,
    scope: CredentialScope = CredentialScope.AUDIT,
) -> BankCredential:
    """Opt-in store of a bank password / derivation inputs, encrypted at rest."""
    if not get_settings().allow_credential_storage:
        raise CredentialStorageDisabled("credential storage is disabled")
    cred = BankCredential(
        scope=scope.value,
        scope_id=scope_id,
        bank=bank.value,
        label=label,
        secret_ciphertext=literal_to_ciphertext(literal) if literal else None,
        context_ciphertext=context_to_ciphertext(context) if context else None,
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)
    return cred


def resolve_candidates(
    session: Session,
    scope_id: str,
    bank: Bank,
    typed_password: str | None = None,
    extra_context: CredentialContext | None = None,
) -> list[str]:
    """Full candidate list for an unlock, in priority order:
    typed → saved literal → derived(saved inputs) → derived(audit subject inputs).

    `extra_context` lets the caller feed the audit's own subject data (name/DOB)
    so a bank's format derives without a separately-saved credential.
    """
    saved_literal: str | None = None
    context: CredentialContext | None = None
    cred = get_saved_credential(session, scope_id, bank)
    if cred is not None:
        if cred.secret_ciphertext:
            saved_literal = literal_from_ciphertext(cred.secret_ciphertext)
        if cred.context_ciphertext:
            context = context_from_ciphertext(cred.context_ciphertext)

    cands = build_candidates(
        bank,
        typed_password=typed_password,
        saved_literal=saved_literal,
        context=context,
    )
    if extra_context is not None:
        for pw in candidates_for_bank(bank, extra_context):
            if pw not in cands:
                cands.append(pw)
    return cands
