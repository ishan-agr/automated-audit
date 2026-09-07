"""Audit id value object: the short, URL-safe "uid as enum" handle `AUD-XXXXXX`.

Derived from a ULID (time-ordered) → Crockford base32 tail → prefixed. Collisions
are astronomically unlikely at 6 chars for a personal tool, but callers should
still check on insert and regenerate on the rare clash.
"""

from __future__ import annotations

from ulid import ULID

_PREFIX = "AUD-"
_TAIL = 6


def new_audit_id() -> str:
    # ULID string is Crockford base32 already; take the last N chars.
    return _PREFIX + str(ULID())[-_TAIL:]


def is_audit_id(value: str) -> bool:
    if not value.startswith(_PREFIX):
        return False
    tail = value[len(_PREFIX) :]
    return len(tail) == _TAIL and tail.isalnum() and tail.upper() == tail
