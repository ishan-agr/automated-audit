"""ReportDefinition + AuditNode + AuditEdge — the persisted card/operation graph.

Versioned so editing never corrupts a generated report; `is_active` marks the
graph that `generate` evaluates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class ReportDefinition(SQLModel, table=True):
    __tablename__ = "report_definitions"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    audit_id: str = Field(index=True)
    name: str = Field(default="Audit report")
    version: int = Field(default=1)
    is_active: bool = Field(default=True)
    canvas: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditNode(SQLModel, table=True):
    __tablename__ = "audit_nodes"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    report_id: str = Field(index=True)
    kind: str = Field()  # TXN_GROUP|AGGREGATE|OPERATION|CONSTANT|RECONCILE|OUTPUT
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    ui: dict = Field(default_factory=dict, sa_column=Column(JSON))


class AuditEdge(SQLModel, table=True):
    __tablename__ = "audit_edges"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    report_id: str = Field(index=True)
    source_node: str = Field()
    target_node: str = Field()
    target_port: str = Field(default="in")
