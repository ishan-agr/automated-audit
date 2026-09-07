"""Report DAG engine tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.report.engine import Edge, GraphError, Node, evaluate
from app.report.reconcile import reconcile
from app.transactions.models import Direction, ExtractedTransaction


def tx(direction, amount, channel="UPI", name=None, ref="r", row=0):
    return ExtractedTransaction(
        id=f"{direction.value}-{amount}-{ref}-{row}",
        audit_id="A",
        document_id="D",
        source_account="ACC1",
        tran_date=date(2026, 4, 1),
        direction=direction.value,
        amount=Decimal(amount),
        channel=channel,
        counterparty_name=name,
        ref_id=ref,
        confidence=0.99,
        row_index=row,
    )


TXNS = [
    tx(Direction.DEBIT, "710", name="Google", ref="a", row=1),
    tx(Direction.DEBIT, "45", name="Vicky", ref="b", row=2),
    tx(Direction.CREDIT, "113900", channel="NEFT", name="Magure", ref="c", row=3),
]
RECON = reconcile(list(TXNS))


def test_sum_of_all_debits():
    nodes = [
        Node("g", "TXN_GROUP", {"selector": {"direction": "DEBIT"}}),
        Node("s", "AGGREGATE", {"fn": "SUM"}),
        Node("o", "OUTPUT", {"label": "Total spend", "format": "CURRENCY"}),
    ]
    edges = [Edge("g", "s"), Edge("s", "o")]
    res = evaluate(nodes, edges, TXNS, RECON)
    assert res.outputs[0]["value"] == "755.00"
    assert res.outputs[0]["label"] == "Total spend"


def test_net_aggregate():
    nodes = [
        Node("g", "TXN_GROUP", {"selector": {"all": True}}),
        Node("n", "AGGREGATE", {"fn": "NET"}),
        Node("o", "OUTPUT", {"label": "Net"}),
    ]
    res = evaluate(nodes, [Edge("g", "n"), Edge("n", "o")], TXNS, RECON)
    assert res.outputs[0]["value"] == "113145.00"  # 113900 - 755


def test_count_by_channel():
    nodes = [
        Node("g", "TXN_GROUP", {"selector": {"channel": "UPI"}}),
        Node("c", "AGGREGATE", {"fn": "COUNT"}),
        Node("o", "OUTPUT", {}),
    ]
    res = evaluate(nodes, [Edge("g", "c"), Edge("c", "o")], TXNS, RECON)
    assert res.outputs[0]["value"] == "2"


def test_operation_between_constants():
    nodes = [
        Node("a", "CONSTANT", {"value": 100}),
        Node("b", "CONSTANT", {"value": 25}),
        Node("op", "OPERATION", {"op": "SUB"}),
        Node("o", "OUTPUT", {}),
    ]
    edges = [Edge("a", "op", "a"), Edge("b", "op", "b"), Edge("op", "o")]
    res = evaluate(nodes, edges, TXNS, RECON)
    assert res.outputs[0]["value"] == "75.00"


def test_division_by_zero_warns():
    nodes = [
        Node("a", "CONSTANT", {"value": 100}),
        Node("b", "CONSTANT", {"value": 0}),
        Node("op", "OPERATION", {"op": "DIV"}),
        Node("o", "OUTPUT", {}),
    ]
    edges = [Edge("a", "op", "a"), Edge("b", "op", "b"), Edge("op", "o")]
    res = evaluate(nodes, edges, TXNS, RECON)
    assert res.outputs[0]["value"] is None
    assert any("zero" in w for w in res.warnings)


def test_reconcile_node_exposes_field():
    nodes = [
        Node("r", "RECONCILE", {"field": "total_debit"}),
        Node("o", "OUTPUT", {"label": "Debit"}),
    ]
    res = evaluate(nodes, [Edge("r", "o")], TXNS, RECON)
    assert res.outputs[0]["value"] == "755.00"


def test_cycle_rejected():
    nodes = [Node("a", "CONSTANT", {"value": 1}), Node("b", "CONSTANT", {"value": 2})]
    edges = [Edge("a", "b"), Edge("b", "a")]
    with pytest.raises(GraphError):
        evaluate(nodes, edges, TXNS, RECON)
