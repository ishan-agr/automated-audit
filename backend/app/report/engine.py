"""Report compute engine — pure, deterministic evaluation of the card/operation
DAG on top of the reconciled transaction view (LLD §3).

Node kinds:
  TXN_GROUP  — filter txns by a selector  → TxnSet
  AGGREGATE  — reduce a TxnSet            → scalar (SUM|COUNT|AVG|MIN|MAX|NET)
  OPERATION  — math on scalar inputs      → scalar (ADD|SUB|MUL|DIV|PCT)
  CONSTANT   — a fixed number             → scalar
  RECONCILE  — a field of the recon result→ scalar
  OUTPUT     — a formatted report line

Wiring is by edges (source→target, ordered by `target_port`). Evaluated in
topological order; cycles are rejected. Everything is Decimal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from app.report.reconcile import ReconciliationResult
from app.transactions.models import Direction, ExtractedTransaction

_CENT = Decimal("0.01")


class GraphError(ValueError):
    """Invalid graph (cycle, bad wiring, unknown node kind)."""


@dataclass
class Node:
    id: str
    kind: str
    config: dict = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    target_port: str = "in"


@dataclass
class EvalResult:
    outputs: list[dict]
    node_values: dict
    warnings: list[str]


# --------------------------------------------------------------------------- #
# selector matching (TXN_GROUP)
# --------------------------------------------------------------------------- #

def _field_value(t: ExtractedTransaction, key: str) -> str | None:
    key = key.upper()
    if key == "LABEL":
        return t.user_label
    if key == "CHANNEL":
        return t.channel
    if key == "ACCOUNT_NO":
        return t.source_account
    if key == "NAME":
        return t.counterparty_name or (t.identifiers or {}).get("NAME")
    return (t.identifiers or {}).get(key)


def _matches(t: ExtractedTransaction, sel: dict) -> bool:
    if sel.get("direction") and t.direction != sel["direction"]:
        return False
    if sel.get("channel") and t.channel != sel["channel"]:
        return False
    if sel.get("exclude_internal_transfers") and t.is_internal_transfer:
        return False
    key = sel.get("key")
    if key:
        op = (sel.get("op") or "EQ").upper()
        val = _field_value(t, key)
        if op == "EQ":
            if val != sel.get("value"):
                return False
        elif op == "CONTAINS":
            if not val or sel.get("value", "").lower() not in val.lower():
                return False
        elif op == "IN":
            if val not in (sel.get("values") or []):
                return False
        elif op == "REGEX":
            if not val or not re.search(sel.get("value", ""), val):
                return False
        else:
            raise GraphError(f"unknown selector op '{op}'")
    return True


def _select(txns: list[ExtractedTransaction], sel: dict) -> list[ExtractedTransaction]:
    if sel.get("all"):
        pool = txns
    else:
        pool = [t for t in txns if _matches(t, sel)]
    if sel.get("exclude_internal_transfers"):
        pool = [t for t in pool if not t.is_internal_transfer]
    return pool


# --------------------------------------------------------------------------- #
# aggregate
# --------------------------------------------------------------------------- #

def _q(x: Decimal) -> Decimal:
    return x.quantize(_CENT)


def _signed_sum(txset: list[ExtractedTransaction]) -> Decimal:
    total = Decimal("0")
    for t in txset:
        total += t.amount if t.direction == Direction.CREDIT.value else -t.amount
    return total


def _aggregate(txset: list[ExtractedTransaction], fn: str) -> Decimal | None:
    fn = fn.upper()
    amounts = [t.amount for t in txset]
    if fn == "COUNT":
        return Decimal(len(txset))
    if fn == "SUM":
        return _q(sum(amounts, Decimal("0")))
    if fn == "NET":
        return _q(_signed_sum(txset))
    if not amounts:
        return None
    if fn == "AVG":
        return _q(sum(amounts, Decimal("0")) / Decimal(len(amounts)))
    if fn == "MIN":
        return _q(min(amounts))
    if fn == "MAX":
        return _q(max(amounts))
    raise GraphError(f"unknown aggregate fn '{fn}'")


# --------------------------------------------------------------------------- #
# operation
# --------------------------------------------------------------------------- #

def _operate(op: str, a: Decimal, b: Decimal, warnings: list[str]) -> Decimal | None:
    op = op.upper()
    try:
        if op == "ADD":
            return _q(a + b)
        if op == "SUB":
            return _q(a - b)
        if op == "MUL":
            return _q(a * b)
        if op == "DIV":
            if b == 0:
                warnings.append("division by zero")
                return None
            return _q(a / b)
        if op == "PCT":
            if b == 0:
                warnings.append("percent of zero")
                return None
            return _q(a / b * Decimal("100"))
    except InvalidOperation as exc:
        warnings.append(f"math error: {exc}")
        return None
    raise GraphError(f"unknown operation '{op}'")


# --------------------------------------------------------------------------- #
# recon field access
# --------------------------------------------------------------------------- #

def _recon_field(recon: ReconciliationResult, fieldname: str) -> Decimal | None:
    mapping = {
        "net": recon.net,
        "total_debit": recon.total_debit,
        "total_credit": recon.total_credit,
        "txn_count": Decimal(recon.txn_count),
        "internal_transfer_total": recon.internal_transfer_total,
        "coverage_pct": (
            Decimal(str(recon.coverage_pct)) if recon.coverage_pct is not None else None
        ),
        "dedup_removed": Decimal(recon.dedup_removed),
    }
    if fieldname not in mapping:
        raise GraphError(f"unknown reconcile field '{fieldname}'")
    return mapping[fieldname]


# --------------------------------------------------------------------------- #
# topological evaluation
# --------------------------------------------------------------------------- #

def _topo_order(nodes: list[Node], edges: list[Edge]) -> list[str]:
    ids = {n.id for n in nodes}
    for e in edges:
        if e.source not in ids or e.target not in ids:
            raise GraphError(f"edge references unknown node: {e.source}->{e.target}")
    indeg = {n.id: 0 for n in nodes}
    adj: dict[str, list[str]] = {n.id: [] for n in nodes}
    for e in edges:
        adj[e.source].append(e.target)
        indeg[e.target] += 1
    queue = [nid for nid, d in indeg.items() if d == 0]
    order: list[str] = []
    while queue:
        nid = queue.pop(0)
        order.append(nid)
        for nxt in adj[nid]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(nodes):
        raise GraphError("graph has a cycle")
    return order


def evaluate(
    nodes: list[Node],
    edges: list[Edge],
    txns: list[ExtractedTransaction],
    recon: ReconciliationResult,
) -> EvalResult:
    node_by_id = {n.id: n for n in nodes}
    incoming: dict[str, list[Edge]] = {n.id: [] for n in nodes}
    for e in edges:
        incoming[e.target].append(e)

    values: dict = {}
    warnings: list[str] = []

    def scalar_inputs(nid: str) -> list[Decimal | None]:
        ins = sorted(incoming[nid], key=lambda e: e.target_port)
        return [values.get(e.source) for e in ins]

    for nid in _topo_order(nodes, edges):
        node = node_by_id[nid]
        kind = node.kind.upper()
        cfg = node.config or {}
        if kind == "TXN_GROUP":
            values[nid] = _select(txns, cfg.get("selector", {}))
        elif kind == "CONSTANT":
            values[nid] = _q(Decimal(str(cfg.get("value", 0))))
        elif kind == "RECONCILE":
            values[nid] = _recon_field(recon, cfg.get("field", "net"))
        elif kind == "AGGREGATE":
            ins = scalar_inputs(nid)
            txset = ins[0] if ins and isinstance(ins[0], list) else []
            values[nid] = _aggregate(txset, cfg.get("fn", "SUM"))
        elif kind == "OPERATION":
            ins = scalar_inputs(nid)
            a = ins[0] if len(ins) > 0 else None
            b = ins[1] if len(ins) > 1 else cfg.get("constant")
            if isinstance(b, (int, float, str)) and not isinstance(b, Decimal):
                b = Decimal(str(b))
            if a is None or b is None:
                warnings.append(f"operation node {nid} missing input")
                values[nid] = None
            else:
                values[nid] = _operate(cfg.get("op", "ADD"), a, b, warnings)
        elif kind == "OUTPUT":
            ins = scalar_inputs(nid)
            values[nid] = ins[0] if ins else None
        else:
            raise GraphError(f"unknown node kind '{kind}'")

    outputs = []
    for n in nodes:
        if n.kind.upper() == "OUTPUT":
            v = values.get(n.id)
            outputs.append(
                {
                    "node_id": n.id,
                    "label": (n.config or {}).get("label", n.id),
                    "format": (n.config or {}).get("format", "NUMBER"),
                    "value": (str(v) if isinstance(v, Decimal) else v),
                }
            )
    # TxnSets aren't JSON-friendly; expose only scalar node values.
    scalar_values = {
        k: (str(v) if isinstance(v, Decimal) else (len(v) if isinstance(v, list) else v))
        for k, v in values.items()
    }
    return EvalResult(outputs=outputs, node_values=scalar_values, warnings=warnings)
