"""Axis Bank statement profile — parse Docling table grids into raw transactions.

Column order: [Tran Date | Particulars | Debit | Credit | Balance | Init.Br].
The header row appears only on the first table; later tables have none (Docling
promotes their first data row to columns), so we treat every non-header row as
data. Special rows (OPENING/CLOSING BALANCE, TRANSACTION TOTAL) are captured for
reconciliation rather than emitted as transactions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from app.extraction.tables import PageTable
from app.transactions.models import Direction

_DATE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")
_HEADER_HINT = ("tran date", "particulars")
_ACCOUNT_PERIOD = re.compile(
    r"Account No:\s*(\d+)\s*for the period\s*\(From:\s*([\d-]+)\s*To:\s*([\d-]+)\)",
    re.IGNORECASE,
)


@dataclass
class RawTxn:
    page_num: int
    row_index: int
    tran_date: date | None
    narration: str
    direction: str
    amount: Decimal
    balance: Decimal | None


@dataclass
class ParsedStatement:
    txns: list[RawTxn] = field(default_factory=list)
    opening_balance: Decimal | None = None
    closing_balance: Decimal | None = None
    total_debit: Decimal | None = None
    total_credit: Decimal | None = None


def parse_amount(s: str) -> Decimal | None:
    s = (s or "").replace(",", "").replace("₹", "").strip()
    if not s or s in {"-", "--"}:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_date(s: str) -> date | None:
    m = _DATE.match((s or "").strip())
    if not m:
        return None
    dd, mm, yyyy = (int(x) for x in m.groups())
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        return None


def _is_header(cells: list[str]) -> bool:
    joined = " ".join(str(c).lower() for c in cells)
    return any(h in joined for h in _HEADER_HINT)


def _pad(row: list[str], n: int = 6) -> list[str]:
    row = [("" if c is None else str(c)).strip() for c in row]
    return row + [""] * (n - len(row)) if len(row) < n else row[:n]


def parse_axis_header(text: str) -> dict:
    """Pull account no + statement period from the (clean) statement line."""
    out: dict = {}
    m = _ACCOUNT_PERIOD.search(text or "")
    if m:
        out["account_no"] = m.group(1)
        pf, pt = parse_date(m.group(2)), parse_date(m.group(3))
        if pf:
            out["period_from"] = pf.isoformat()
        if pt:
            out["period_to"] = pt.isoformat()
    return out


def parse_axis_tables(tables: list[PageTable]) -> ParsedStatement:
    stmt = ParsedStatement()
    row_index = 0
    for table in sorted(tables, key=lambda t: t.page_num):
        for raw in table.rows:
            cells = _pad(raw)
            if _is_header(cells):
                continue
            date_s, narration, debit_s, credit_s, balance_s, _init = cells
            label = narration.upper()

            if "OPENING BALANCE" in label:
                stmt.opening_balance = parse_amount(balance_s)
                continue
            if "CLOSING BALANCE" in label:
                stmt.closing_balance = parse_amount(balance_s)
                continue
            if "TRANSACTION TOTAL" in label:
                stmt.total_debit = parse_amount(debit_s)
                stmt.total_credit = parse_amount(credit_s)
                continue

            debit = parse_amount(debit_s)
            credit = parse_amount(credit_s)
            if debit is None and credit is None:
                continue  # not a transaction row (noise / continuation)

            direction = Direction.DEBIT.value if debit is not None else Direction.CREDIT.value
            amount = debit if debit is not None else credit
            stmt.txns.append(
                RawTxn(
                    page_num=table.page_num,
                    row_index=row_index,
                    tran_date=parse_date(date_s),
                    narration=narration,
                    direction=direction,
                    amount=amount,  # type: ignore[arg-type]
                    balance=parse_amount(balance_s),
                )
            )
            row_index += 1
    return stmt
