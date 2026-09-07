"""Application settings (env-driven).

Only the fields needed by the current slice are defined; add as modules land.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUDIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Local, single-user deployment (decision v1). Postgres in real deployments;
    # sqlite default keeps `alembic`/local dev frictionless.
    database_url: str = "sqlite:///./automated_audit.db"

    # Fernet key (urlsafe base64, 32 bytes) used to encrypt stored bank
    # credentials at rest. MUST be set in any real deployment. When unset we
    # derive an ephemeral dev key and log a warning (see core.crypto).
    secret_key: str | None = None

    # Opt-in: allow persisting bank statement passwords / derivation inputs.
    # Even when a user asks to "save the password for this bank", nothing is
    # stored unless this is true — a global safety switch.
    allow_credential_storage: bool = True

    # Local object store root (uploaded originals + unlocked working copies).
    data_dir: str = "./data"

    # Extraction job pool: bound concurrent extractions (job pooling). Run jobs
    # inline (await in-request) when true — deterministic for tests / simple local.
    max_extract_concurrency: int = 2
    inline_jobs: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
