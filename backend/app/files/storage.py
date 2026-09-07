"""Object storage abstraction. `LocalFileStore` (filesystem) for local dev;
swap to an S3/MinIO impl behind the same `FileStore` protocol later.

Keys are POSIX-style paths, e.g. `original/<sha256>.bin`, `work/<doc_id>.pdf`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class FileStore(Protocol):
    def save(self, key: str, data: bytes) -> None: ...
    def load(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...


class LocalFileStore:
    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)

    def _path(self, key: str) -> Path:
        p = (self._base / key).resolve()
        base = self._base.resolve()
        if base not in p.parents and p != base:
            raise ValueError(f"key escapes store root: {key}")
        return p

    def save(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def load(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


_store: LocalFileStore | None = None


def get_store() -> FileStore:
    global _store
    if _store is None:
        _store = LocalFileStore(get_settings().data_dir)
    return _store
