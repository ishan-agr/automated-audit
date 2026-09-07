"""Report service: persist/load the card graph, and `generate_audit` — the one
operation the date range triggers (reconcile pre-pass + report DAG → one artifact).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlmodel import Session, delete, select

from app.audit.models import Audit
from app.report.engine import Edge, Node, evaluate
from app.report.engine import _topo_order as validate_acyclic
from app.report.models import AuditEdge, AuditNode, ReportDefinition
from app.report.reconcile import ReconciliationResult, reconcile
from app.transactions.models import DocumentMeta, ExtractedTransaction

_ALLOWED_KINDS = {
    "TXN_GROUP", "AGGREGATE", "OPERATION", "CONSTANT", "RECONCILE", "OUTPUT",
}


class AuditNotFound(Exception):
    pass


class InvalidGraph(Exception):
    pass


# --------------------------------------------------------------------------- #
# graph persistence
# --------------------------------------------------------------------------- #

def get_or_create_active_report(session: Session, audit_id: str) -> ReportDefinition:
    rd = session.exec(
        select(ReportDefinition).where(
            ReportDefinition.audit_id == audit_id, ReportDefinition.is_active == True  # noqa: E712
        )
    ).first()
    if rd is None:
        rd = ReportDefinition(audit_id=audit_id)
        session.add(rd)
        session.commit()
        session.refresh(rd)
    return rd


def save_graph(
    session: Session, audit_id: str, nodes: list[dict], edges: list[dict], name: str | None = None
) -> dict:
    if session.get(Audit, audit_id) is None:
        raise AuditNotFound(audit_id)

    eng_nodes = [Node(n["id"], n["kind"], n.get("config", {})) for n in nodes]
    eng_edges = [
        Edge(e["source"], e["target"], e.get("target_port", "in")) for e in edges
    ]
    for n in eng_nodes:
        if n.kind.upper() not in _ALLOWED_KINDS:
            raise InvalidGraph(f"unknown node kind '{n.kind}'")
    try:
        validate_acyclic(eng_nodes, eng_edges)  # raises on cycle / bad edge
    except Exception as exc:
        raise InvalidGraph(str(exc)) from exc

    rd = get_or_create_active_report(session, audit_id)
    if name:
        rd.name = name
    session.exec(delete(AuditNode).where(AuditNode.report_id == rd.id))
    session.exec(delete(AuditEdge).where(AuditEdge.report_id == rd.id))
    for n in nodes:
        session.add(
            AuditNode(
                id=n["id"],
                report_id=rd.id,
                kind=n["kind"],
                config=n.get("config", {}),
                ui=n.get("ui", {}),
            )
        )
    for e in edges:
        session.add(
            AuditEdge(
                report_id=rd.id,
                source_node=e["source"],
                target_node=e["target"],
                target_port=e.get("target_port", "in"),
            )
        )
    rd.updated_at = datetime.now(UTC)
    session.add(rd)
    session.commit()
    return load_graph(session, audit_id)


def load_graph(session: Session, audit_id: str) -> dict:
    rd = session.exec(
        select(ReportDefinition).where(
            ReportDefinition.audit_id == audit_id, ReportDefinition.is_active == True  # noqa: E712
        )
    ).first()
    if rd is None:
        return {"report_id": None, "name": None, "nodes": [], "edges": []}
    nodes = session.exec(select(AuditNode).where(AuditNode.report_id == rd.id)).all()
    edges = session.exec(select(AuditEdge).where(AuditEdge.report_id == rd.id)).all()
    return {
        "report_id": rd.id,
        "name": rd.name,
        "nodes": [{"id": n.id, "kind": n.kind, "config": n.config, "ui": n.ui} for n in nodes],
        "edges": [
            {"source": e.source_node, "target": e.target_node, "target_port": e.target_port}
            for e in edges
        ],
    }


def _engine_graph(session: Session, audit_id: str) -> tuple[list[Node], list[Edge]]:
    g = load_graph(session, audit_id)
    nodes = [Node(n["id"], n["kind"], n.get("config", {})) for n in g["nodes"]]
    edges = [Edge(e["source"], e["target"], e.get("target_port", "in")) for e in g["edges"]]
    return nodes, edges


# --------------------------------------------------------------------------- #
# generate = reconcile pre-pass + report DAG
# --------------------------------------------------------------------------- #

def _d(x: Decimal | None) -> str | None:
    return str(x) if x is not None else None


def recon_to_dict(r: ReconciliationResult) -> dict:
    return {
        "total_debit": _d(r.total_debit),
        "total_credit": _d(r.total_credit),
        "net": _d(r.net),
        "txn_count": r.txn_count,
        "dedup_removed": r.dedup_removed,
        "internal_transfer_total": _d(r.internal_transfer_total),
        "coverage_pct": r.coverage_pct,
        "flagged_low_confidence": r.flagged_low_confidence,
        "gaps": [
            {"account": g.account, "start": g.start.isoformat(), "end": g.end.isoformat()}
            for g in r.gaps
        ],
        "accounts": [
            {
                "account": a.account,
                "opening": _d(a.opening),
                "closing_stated": _d(a.closing_stated),
                "closing_computed": _d(a.closing_computed),
                "sum_debit": _d(a.sum_debit),
                "sum_credit": _d(a.sum_credit),
                "net": _d(a.net),
                "txn_count": a.txn_count,
                "continuity_ok": a.continuity_ok,
                "breaks": [
                    {
                        "at_date": b.at_date.isoformat() if b.at_date else None,
                        "expected": _d(b.expected),
                        "found": _d(b.found),
                    }
                    for b in a.breaks
                ],
            }
            for a in r.accounts
        ],
    }


def generate_audit(
    session: Session,
    audit_id: str,
    range_from: date | None = None,
    range_to: date | None = None,
) -> dict:
    audit = session.get(Audit, audit_id)
    if audit is None:
        raise AuditNotFound(audit_id)
    rf = range_from or audit.range_from
    rt = range_to or audit.range_to

    stmt = select(ExtractedTransaction).where(ExtractedTransaction.audit_id == audit_id)
    if rf:
        stmt = stmt.where(ExtractedTransaction.tran_date >= rf)
    if rt:
        stmt = stmt.where(ExtractedTransaction.tran_date <= rt)
    txns = list(session.exec(stmt))

    statements: list[tuple[str, date, date]] = []
    for m in session.exec(select(DocumentMeta).where(DocumentMeta.audit_id == audit_id)):
        pf, pt = m.kv.get("period_from"), m.kv.get("period_to")
        if pf and pt:
            statements.append(
                (m.kv.get("account_no", ""), date.fromisoformat(pf), date.fromisoformat(pt))
            )
    window = (rf, rt) if rf and rt else None
    recon = reconcile(txns, statements=statements or None, window=window)

    nodes, edges = _engine_graph(session, audit_id)
    outputs, warnings = [], []
    if nodes:
        ev = evaluate(nodes, edges, txns, recon)
        outputs, warnings = ev.outputs, ev.warnings

    return {
        "audit_id": audit_id,
        "range": {
            "from": rf.isoformat() if rf else None,
            "to": rt.isoformat() if rt else None,
        },
        "reconciliation": recon_to_dict(recon),
        "outputs": outputs,
        "warnings": warnings,
    }
