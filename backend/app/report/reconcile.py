"""Reconcile pre-pass (LLD §2.6) — the innate audit output over multiple merged
sources. Pure function over `ExtractedTransaction` rows filtered to a date range:

  1. overlap de-duplication (same txn in two overlapping statements),
  2. per-account balance continuity (chained opening→closing),
  3. own-account transfer netting (don't double-count money moved between your
     own accounts),
  4. coverage / gap detection vs the required window,
  5. a per-account + rolled-up reconciliation summary.

Operates on in-memory objects so it is fully unit-testable without a DB, and
re-runs cheaply on every range change (regenerate, never re-extract).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.transactions.models import Direction, ExtractedTransaction

_CENT = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(_CENT)


def _narr_hash(s: str) -> str:
    return hashlib.sha1((s or "").strip().lower().encode()).hexdigest()[:12]


# --------------------------------------------------------------------------- #
# 1. overlap de-duplication
# --------------------------------------------------------------------------- #

def _dedup_key(t: ExtractedTransaction) -> tuple:
    return (
        t.source_account or "",
        t.tran_date,
        str(_q(t.amount)),
        t.direction,
        t.ref_id or (str(_q(t.balance)) if t.balance is not None else ""),
        _narr_hash(t.narration_raw),
    )


def dedupe(txns: list[ExtractedTransaction]) -> tuple[list[ExtractedTransaction], int]:
    seen: dict[tuple, ExtractedTransaction] = {}
    canonical: list[ExtractedTransaction] = []
    removed = 0
    for t in txns:
        key = _dedup_key(t)
        if key in seen:
            t.superseded_by = seen[key].id
            removed += 1
        else:
            seen[key] = t
            canonical.append(t)
    return canonical, removed


# --------------------------------------------------------------------------- #
# 2. own-account transfer netting
# --------------------------------------------------------------------------- #

def detect_internal_transfers(
    txns: list[ExtractedTransaction], *, day_window: int = 3
) -> Decimal:
    """Match a DEBIT in one account to a CREDIT in another for the same amount
    within `day_window` days; flag both `is_internal_transfer`. Returns the total
    transferred (one side). Greedy 1:1 pairing."""
    debits = [t for t in txns if t.direction == Direction.DEBIT.value]
    credits = [t for t in txns if t.direction == Direction.CREDIT.value]
    used: set[str] = set()
    total = Decimal("0")
    for d in debits:
        for c in credits:
            if c.id in used:
                continue
            if (d.source_account or "") == (c.source_account or ""):
                continue  # must cross accounts
            if _q(d.amount) != _q(c.amount):
                continue
            if d.tran_date is None or c.tran_date is None:
                continue
            if abs((d.tran_date - c.tran_date).days) > day_window:
                continue
            d.is_internal_transfer = True
            c.is_internal_transfer = True
            used.add(c.id)
            total += _q(d.amount)
            break
    return _q(total)


# --------------------------------------------------------------------------- #
# 3. per-account balance continuity + summary
# --------------------------------------------------------------------------- #

@dataclass
class ContinuityBreak:
    account: str
    at_date: date | None
    expected: Decimal
    found: Decimal


@dataclass
class AccountRecon:
    account: str
    opening: Decimal | None
    closing_stated: Decimal | None
    closing_computed: Decimal
    sum_debit: Decimal
    sum_credit: Decimal
    net: Decimal
    txn_count: int
    continuity_ok: bool
    breaks: list[ContinuityBreak] = field(default_factory=list)


def _signed(t: ExtractedTransaction) -> Decimal:
    a = _q(t.amount)
    return a if t.direction == Direction.CREDIT.value else -a


def reconcile_account(account: str, txns: list[ExtractedTransaction]) -> AccountRecon:
    ordered = sorted(txns, key=lambda t: (t.tran_date or date.min, t.row_index or 0))
    debit = Direction.DEBIT.value
    credit = Direction.CREDIT.value
    sum_debit = _q(sum((_q(t.amount) for t in ordered if t.direction == debit), Decimal("0")))
    sum_credit = _q(sum((_q(t.amount) for t in ordered if t.direction == credit), Decimal("0")))
    net = _q(sum_credit - sum_debit)

    opening: Decimal | None = None
    closing_stated: Decimal | None = None
    breaks: list[ContinuityBreak] = []
    with_bal = [t for t in ordered if t.balance is not None]
    if with_bal:
        first = with_bal[0]
        opening = _q(first.balance - _signed(first))
        closing_stated = _q(with_bal[-1].balance)
        prev = first
        for cur in with_bal[1:]:
            expected = _q(prev.balance + _signed(cur))
            if expected != _q(cur.balance):
                breaks.append(
                    ContinuityBreak(account, cur.tran_date, expected, _q(cur.balance))
                )
            prev = cur

    closing_computed = _q((opening or Decimal("0")) + net)
    return AccountRecon(
        account=account,
        opening=opening,
        closing_stated=closing_stated,
        closing_computed=closing_computed,
        sum_debit=sum_debit,
        sum_credit=sum_credit,
        net=net,
        txn_count=len(ordered),
        continuity_ok=not breaks and (closing_stated is None or closing_stated == closing_computed),
        breaks=breaks,
    )


# --------------------------------------------------------------------------- #
# 4. coverage / gaps
# --------------------------------------------------------------------------- #

@dataclass
class Gap:
    account: str
    start: date
    end: date


def coverage(
    statements: list[tuple[str, date, date]],
    window_from: date,
    window_to: date,
) -> tuple[float, list[Gap]]:
    """statements = (account, period_from, period_to). Returns (coverage%, gaps)
    across the union of accounts within the window."""
    if window_to < window_from:
        return 0.0, []
    total_days = (window_to - window_from).days + 1
    accounts = {a for a, _, _ in statements} or {""}
    covered_all: set[date] = set()
    gaps: list[Gap] = []
    for acct in accounts:
        covered: set[date] = set()
        for a, pf, pt in statements:
            if a != acct:
                continue
            d = max(pf, window_from)
            end = min(pt, window_to)
            while d <= end:
                covered.add(d)
                d += timedelta(days=1)
        covered_all |= covered
        # gaps for this account within the window
        gap_start = None
        d = window_from
        while d <= window_to:
            if d not in covered:
                gap_start = gap_start or d
            elif gap_start is not None:
                gaps.append(Gap(acct, gap_start, d - timedelta(days=1)))
                gap_start = None
            d += timedelta(days=1)
        if gap_start is not None:
            gaps.append(Gap(acct, gap_start, window_to))
    pct = round(100.0 * len(covered_all) / total_days, 1)
    return pct, gaps


# --------------------------------------------------------------------------- #
# top-level
# --------------------------------------------------------------------------- #

@dataclass
class ReconciliationResult:
    accounts: list[AccountRecon]
    total_debit: Decimal
    total_credit: Decimal
    net: Decimal
    txn_count: int
    dedup_removed: int
    internal_transfer_total: Decimal
    coverage_pct: float | None
    gaps: list[Gap]
    flagged_low_confidence: int


def reconcile(
    txns: list[ExtractedTransaction],
    *,
    statements: list[tuple[str, date, date]] | None = None,
    window: tuple[date, date] | None = None,
    confidence_floor: float = 0.5,
) -> ReconciliationResult:
    canonical, removed = dedupe(list(txns))
    transfer_total = detect_internal_transfers(canonical)

    by_account: dict[str, list[ExtractedTransaction]] = {}
    for t in canonical:
        by_account.setdefault(t.source_account or "", []).append(t)
    accounts = [reconcile_account(a, ts) for a, ts in sorted(by_account.items())]

    cov_pct: float | None = None
    gaps: list[Gap] = []
    if statements is not None and window is not None:
        cov_pct, gaps = coverage(statements, window[0], window[1])

    total_debit = _q(sum((a.sum_debit for a in accounts), Decimal("0")))
    total_credit = _q(sum((a.sum_credit for a in accounts), Decimal("0")))
    flagged = sum(1 for t in canonical if t.confidence < confidence_floor)

    return ReconciliationResult(
        accounts=accounts,
        total_debit=total_debit,
        total_credit=total_credit,
        net=_q(total_credit - total_debit),
        txn_count=len(canonical),
        dedup_removed=removed,
        internal_transfer_total=transfer_total,
        coverage_pct=cov_pct,
        gaps=gaps,
        flagged_low_confidence=flagged,
    )
