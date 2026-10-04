"""Generic CSV / XLSX statement profile — best-effort parser for UPI-app exports
(GPay / PhonePe / Paytm) and bank CSV downloads.

These exports have no fixed schema, so we detect the header row and map columns
to fields by keyword. Direction comes from separate debit/credit columns, a
type/DR-CR column, or a signed amount — whichever the file provides. Output is
the same `ParsedStatement` / `RawTxn` shape the Axis PDF profile produces, so it
feeds the identical narration + persistence pipeline.

No layout model, no OCR — just pandas. Tune the keyword sets in `_RULES` as real
sample exports arrive.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from app.bank_profiles.axis import ParsedStatement, RawTxn, parse_amount
from app.transactions.models import Direction

_SPREADSHEET_SUFFIXES = {".csv", ".xls", ".xlsx"}


def is_tabular(filename: str) -> bool:
    return Path(filename).suffix.lower() in _SPREADSHEET_SUFFIXES


def _norm(s: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


_TYPE_EXACT = {
    "type",
    "txntype",
    "transactiontype",
    "drcr",
    "crdr",
    "debitcredit",
    "creditdebit",
    "direction",
}

# (field, tokens) — first field with a substring hit wins. Order matters:
# debit/credit before amount so "debitamount" maps to debit, not amount.
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("date", ("date", "datetime", "timestamp")),
    ("balance", ("balance",)),
    (
        "refid",
        ("refno", "reference", "utr", "transactionid", "txnid", "upiref",
         "rrn", "orderid", "cheque"),
    ),
    ("debit", ("debit", "withdrawal", "moneyout")),
    ("credit", ("credit", "deposit", "moneyin")),
    ("amount", ("amount", "amt")),
    (
        "desc",
        ("description", "narration", "details", "remark", "particular",
         "merchant", "name", "paidto", "receivedfrom", "note", "payee", "payer"),
    ),
]


def _classify(cell: str) -> str | None:
    c = _norm(cell)
    if not c:
        return None
    if c in _TYPE_EXACT:
        return "type"
    for field, tokens in _RULES:
        if any(tok in c for tok in tokens):
            return field
    if c == "dr":
        return "debit"
    if c == "cr":
        return "credit"
    return None


_DATE_FORMATS = (
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d-%m-%y",
    "%d/%m/%y",
    "%m/%d/%Y",
    "%d %B %Y",
    "%b %d, %Y",
)


def parse_any_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    # keep only the date portion if a time is appended
    token = re.split(r"[ tT]", s, maxsplit=1)[0] if re.search(r"\d[ tT]\d", s) else s
    for candidate in (s, token):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(candidate.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _read_rows(data: bytes, filename: str) -> list[list[str]]:
    suffix = Path(filename).suffix.lower()
    if suffix in {".xls", ".xlsx"}:
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        rows = [
            ["" if c is None else str(c) for c in row]
            for row in ws.iter_rows(values_only=True)
        ]
        wb.close()
        return rows
    # CSV via the stdlib reader — ragged rows (preamble lines with fewer columns
    # than the header) are handled gracefully, unlike a fixed-width frame reader.
    text = data.decode("utf-8-sig", errors="replace")
    return [[str(c) for c in row] for row in csv.reader(io.StringIO(text))]


def _detect_header(rows: list[list[str]]) -> tuple[int, dict[str, list[int]]] | None:
    """Return (header_row_index, {field: [col indices]}) for the best header row."""
    best: tuple[int, dict[str, list[int]]] | None = None
    best_score = 0
    for i, row in enumerate(rows[:25]):  # header is near the top
        cols: dict[str, list[int]] = {}
        for j, cell in enumerate(row):
            field = _classify(cell)
            if field:
                cols.setdefault(field, []).append(j)
        has_amount = bool(cols.get("amount") or cols.get("debit") or cols.get("credit"))
        score = len(cols)
        if has_amount and cols.get("date") and score > best_score:
            best_score = score
            best = (i, cols)
    return best


def _first(cells: list[str], cols: dict[str, list[int]], field: str) -> str:
    idxs = cols.get(field)
    if not idxs:
        return ""
    i = idxs[0]
    return cells[i] if i < len(cells) else ""


def _amount_direction(
    cells: list[str], cols: dict[str, list[int]]
) -> tuple[Decimal | None, str]:
    if cols.get("debit") or cols.get("credit"):
        debit = parse_amount(_first(cells, cols, "debit"))
        credit = parse_amount(_first(cells, cols, "credit"))
        if debit is not None and debit != 0:
            return abs(debit), Direction.DEBIT.value
        if credit is not None and credit != 0:
            return abs(credit), Direction.CREDIT.value
        return None, Direction.DEBIT.value

    amt = parse_amount(_first(cells, cols, "amount"))
    if amt is None:
        return None, Direction.DEBIT.value
    t = _norm(_first(cells, cols, "type"))
    if t:
        credit_hit = t.startswith("cr") or any(
            k in t for k in ("credit", "received", "deposit", "refund")
        )
        debit_hit = t.startswith("dr") or any(
            k in t for k in ("debit", "sent", "paid", "withdraw", "purchase")
        )
        if credit_hit:
            return abs(amt), Direction.CREDIT.value
        if debit_hit:
            return abs(amt), Direction.DEBIT.value
    # signed-amount fallback
    if amt < 0:
        return -amt, Direction.DEBIT.value
    return amt, Direction.CREDIT.value


def parse_tabular(data: bytes, filename: str) -> ParsedStatement:
    rows = _read_rows(data, filename)
    detected = _detect_header(rows)
    if detected is None:
        return ParsedStatement()
    header_idx, cols = detected

    txns: list[RawTxn] = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for offset, cells in enumerate(rows[header_idx + 1 :], start=1):
        if not any(str(c).strip() for c in cells):
            continue
        tran_date = parse_any_date(_first(cells, cols, "date"))
        amount, direction = _amount_direction(cells, cols)
        if amount is None:
            continue
        desc_parts = [
            cells[i]
            for i in cols.get("desc", [])
            if i < len(cells) and str(cells[i]).strip()
        ]
        ref = _first(cells, cols, "refid")
        narration = " ".join(p.strip() for p in desc_parts) or ref
        balance = parse_amount(_first(cells, cols, "balance"))
        txns.append(
            RawTxn(
                page_num=1,
                row_index=offset,
                tran_date=tran_date,
                narration=narration,
                direction=direction,
                amount=amount,
                balance=balance,
            )
        )
        if direction == Direction.DEBIT.value:
            total_debit += amount
        else:
            total_credit += amount

    return ParsedStatement(
        txns=txns,
        total_debit=total_debit if txns else None,
        total_credit=total_credit if txns else None,
    )
