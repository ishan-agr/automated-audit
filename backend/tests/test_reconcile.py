"""Reconcile pre-pass tests (dedup, continuity, transfer netting, coverage)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.report.reconcile import coverage, reconcile
from app.transactions.models import Direction, ExtractedTransaction


def tx(
    *,
    account="ACC1",
    d=date(2026, 4, 1),
    direction=Direction.DEBIT,
    amount="100",
    balance=None,
    ref=None,
    narration="",
    conf=0.99,
    id=None,
    row=0,
):
    return ExtractedTransaction(
        id=id or f"{account}-{d}-{direction.value}-{amount}-{row}",
        audit_id="AUD-TEST",
        document_id="DOC1",
        source_account=account,
        tran_date=d,
        direction=direction.value,
        amount=Decimal(amount),
        balance=Decimal(balance) if balance is not None else None,
        ref_id=ref,
        narration_raw=narration,
        confidence=conf,
        row_index=row,
    )


def test_dedupe_collapses_overlap_duplicates():
    a = tx(ref="R1", amount="710", narration="UPI/x", row=0)
    b = tx(ref="R1", amount="710", narration="UPI/x", row=0, id="dup")
    res = reconcile([a, b])
    assert res.dedup_removed == 1
    assert res.txn_count == 1


def test_balance_continuity_ok():
    txns = [
        tx(direction=Direction.CREDIT, amount="100", balance="1100", ref="c1", row=1),
        tx(direction=Direction.DEBIT, amount="40", balance="1060", ref="d1", row=2),
    ]
    res = reconcile(txns)
    acc = res.accounts[0]
    assert acc.opening == Decimal("1000.00")
    assert acc.closing_stated == Decimal("1060.00")
    assert acc.closing_computed == Decimal("1060.00")
    assert acc.continuity_ok is True


def test_balance_continuity_break_detected():
    txns = [
        tx(direction=Direction.CREDIT, amount="100", balance="1100", ref="c1", row=1),
        tx(direction=Direction.DEBIT, amount="40", balance="1070", ref="d1", row=2),
    ]
    res = reconcile(txns)
    acc = res.accounts[0]
    assert acc.continuity_ok is False
    assert acc.breaks and acc.breaks[0].expected == Decimal("1060.00")


def test_internal_transfer_netting_across_accounts():
    txns = [
        tx(account="A", direction=Direction.DEBIT, amount="15000", d=date(2026, 4, 10), ref="d"),
        tx(account="B", direction=Direction.CREDIT, amount="15000", d=date(2026, 4, 11), ref="c"),
    ]
    res = reconcile(txns)
    assert res.internal_transfer_total == Decimal("15000.00")
    assert all(t.is_internal_transfer for t in txns)


def test_multi_account_totals():
    txns = [
        tx(account="A", direction=Direction.DEBIT, amount="200", ref="a1"),
        tx(account="B", direction=Direction.CREDIT, amount="500", ref="b1"),
    ]
    res = reconcile(txns)
    assert res.total_debit == Decimal("200.00")
    assert res.total_credit == Decimal("500.00")
    assert res.net == Decimal("300.00")
    assert len(res.accounts) == 2


def test_low_confidence_flagged():
    res = reconcile([tx(conf=0.2, ref="x"), tx(conf=0.99, ref="y")])
    assert res.flagged_low_confidence == 1


def test_coverage_and_gaps():
    # window Apr 1–30; statement covers Apr 1–20 → ~70% coverage, one gap 21–30.
    pct, gaps = coverage(
        [("ACC1", date(2026, 4, 1), date(2026, 4, 20))],
        date(2026, 4, 1),
        date(2026, 4, 30),
    )
    assert 66.0 <= pct <= 67.0
    assert gaps and gaps[0].start == date(2026, 4, 21)
    assert gaps[0].end == date(2026, 4, 30)
