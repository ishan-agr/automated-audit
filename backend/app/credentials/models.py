"""BankCredential — opt-in, encrypted-at-rest storage of a bank's statement
password (or the personal inputs to derive it).

Scope: either a single audit or the whole user (reuse across audits). Nothing is
stored unless the user opts in AND `settings.allow_credential_storage` is true.
Exactly one of `secret_ciphertext` (a literal password) or `context_ciphertext`
(derivation inputs) is typically set; both may be set if the user saved a literal
*and* personal inputs. Ciphertext columns hold Fernet tokens — never plaintext.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlmodel import Field, SQLModel


class CredentialScope(str, Enum):
    USER = "USER"
    AUDIT = "AUDIT"


class BankCredential(SQLModel, table=True):
    __tablename__ = "bank_credentials"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    scope: str = Field(default=CredentialScope.AUDIT.value, index=True)
    scope_id: str = Field(index=True)  # audit_id or user_id
    bank: str = Field(index=True)  # bank_profiles.passwords.Bank value
    label: str | None = Field(default=None, max_length=120)

    # Fernet ciphertext, or NULL. See module docstring.
    secret_ciphertext: str | None = Field(default=None)
    context_ciphertext: str | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
