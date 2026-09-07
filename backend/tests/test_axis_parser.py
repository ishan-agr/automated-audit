"""Axis parser tests using the real table shapes Docling produced from the sample."""

from __future__ import annotations

from decimal import Decimal

from app.bank_profiles.axis import parse_axis_header, parse_axis_tables
from app.extraction.tables import PageTable
from app.transactions.models import Direction

# Page 1: real header present.
PAGE1 = PageTable(
    page_num=1,
    rows=[
        ["Tran Date Chq No", "Particulars", "Debit", "Credit", "Balance", "Init. Br"],
        ["", "OPENING BALANCE", "", "", "10966.18", ""],
        ["01-04-2026", "UPI/P2M/645702960479/Google India Digital/UPI/AXIS BANK", "710.00", "", "10256.18", "5016"],
        ["03-04-2026", "NEFT/0811OP6172079607/MAGURE TECH INDIA PRIVATE LI/DBS BANK INDIA LIMIT/", "", "113900.00", "122785.18", "248"],
    ],
)

# Page 8: Docling promoted the first data row to columns (no header) — the
# parser must still treat that first row as a transaction.
PAGE8 = PageTable(
    page_num=8,
    rows=[
        ["02-08-2026", "UPI/P2M/658062692382/SHREE PADMAWATI FOODS/UPI/Kotak Mahindra Bank", "60.00", "", "107909.57", "5016"],
        ["02-08-2026", "UPI/P2M/621459909554/Ankalu pan palace /UPI/YES BANK LIMITED YBS", "135.00", "", "107774.57", "5016"],
        ["", "TRANSACTION TOTAL", "515993.52", "612801.91", "", ""],
        ["", "CLOSING BALANCE", "", "", "107774.57", ""],
    ],
)


def test_parses_special_rows():
    s = parse_axis_tables([PAGE1, PAGE8])
    assert s.opening_balance == Decimal("10966.18")
    assert s.closing_balance == Decimal("107774.57")
    assert s.total_debit == Decimal("515993.52")
    assert s.total_credit == Decimal("612801.91")


def test_parses_transactions():
    s = parse_axis_tables([PAGE1, PAGE8])
    assert len(s.txns) == 4  # 2 from page1 + 2 from page8 (incl. promoted row)

    first = s.txns[0]
    assert first.direction == Direction.DEBIT.value
    assert first.amount == Decimal("710.00")
    assert first.balance == Decimal("10256.18")
    assert first.tran_date.isoformat() == "2026-04-01"

    credit = s.txns[1]
    assert credit.direction == Direction.CREDIT.value
    assert credit.amount == Decimal("113900.00")

    # page-8 first row (promoted from columns) was parsed, not dropped
    assert any(t.amount == Decimal("60.00") for t in s.txns)


def test_header_line_account_and_period():
    text = (
        "Statement of Axis Account No: 924010023017229 for the period "
        "(From: 01-04-2026  To: 02-08-2026)"
    )
    h = parse_axis_header(text)
    assert h["account_no"] == "924010023017229"
    assert h["period_from"] == "2026-04-01"
    assert h["period_to"] == "2026-08-02"
