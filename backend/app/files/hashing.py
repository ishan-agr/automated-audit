"""Streaming SHA-256 of an uploaded file into a spooled temp file.

Keeps peak memory bounded (files under the spool ceiling stay in RAM, larger ones
spill to disk) while producing the content hash used for dedupe.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from typing import BinaryIO

_SPOOL_MAX = 8 * 1024 * 1024  # 8 MB before spilling to disk
_CHUNK = 1024 * 1024  # 1 MB read chunks


@dataclass
class HashedUpload:
    sha256: str
    size: int
    data: bytes  # full bytes (statements are small); read once from the spool


def hash_stream(source: BinaryIO) -> HashedUpload:
    """Read `source` in chunks → (sha256, size, bytes). Sync file-like."""
    h = hashlib.sha256()
    size = 0
    with SpooledTemporaryFile(max_size=_SPOOL_MAX) as spool:
        while True:
            chunk = source.read(_CHUNK)
            if not chunk:
                break
            spool.write(chunk)
            h.update(chunk)
            size += len(chunk)
        spool.seek(0)
        data = spool.read()
    return HashedUpload(sha256=h.hexdigest(), size=size, data=data)
