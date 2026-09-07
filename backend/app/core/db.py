"""Database engine + session helpers (SQLModel).

sqlite by default (local, single-user); Postgres via `AUDIT_DATABASE_URL` in real
deployments. `check_same_thread=False` lets background extraction tasks (asyncio,
same loop/thread) share the engine safely for sqlite.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def init_db() -> None:
    """Create tables. Imports every model module so metadata is populated."""
    from app.audit import models as _audit  # noqa: F401
    from app.credentials import models as _cred  # noqa: F401
    from app.documents import models as _docs  # noqa: F401
    from app.extraction import page_store as _pages  # noqa: F401
    from app.report import models as _report  # noqa: F401
    from app.transactions import models as _txns  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency: a request-scoped session."""
    with Session(get_engine()) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Standalone session for background jobs (own commit/rollback lifecycle)."""
    session = Session(get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
