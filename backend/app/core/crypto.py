"""Symmetric encryption for secrets stored at rest (bank statement passwords /
derivation inputs).

We never store a statement password in plaintext. Storage is opt-in (the user
chooses to save it against a bank); when they do, it is Fernet-encrypted with the
app `secret_key`. Losing the key makes stored secrets unrecoverable — which is the
correct failure mode for a local, single-user tool.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SecretBox:
    """Thin wrapper over Fernet with typed errors and str<->str API."""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:  # wrong key or tampered ciphertext
            raise SecretDecryptError("could not decrypt stored secret") from exc


class SecretDecryptError(RuntimeError):
    """Raised when a stored secret cannot be decrypted (wrong/rotated key)."""


@lru_cache
def get_secret_box() -> SecretBox:
    settings = get_settings()
    key = settings.secret_key
    if not key:
        # Dev fallback: ephemeral key. Secrets encrypted with it will NOT
        # survive a restart — acceptable for local dev, never for real use.
        key = Fernet.generate_key().decode()
        logger.warning(
            "AUDIT_SECRET_KEY not set — using an ephemeral dev key; stored "
            "credentials will not survive a restart. Set AUDIT_SECRET_KEY."
        )
    return SecretBox(key)


def generate_key() -> str:
    """Generate a fresh urlsafe-base64 Fernet key (for `AUDIT_SECRET_KEY`)."""
    return Fernet.generate_key().decode()
