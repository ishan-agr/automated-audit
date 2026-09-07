"""Normalized table structure shared by the extractor adapters and bank parsers.

A `PageTable` is a plain grid of string cells for one detected table on one page.
The Docling adapter produces these; bank parsers consume them. Keeping this dumb
and stringly-typed means parsers are pure and unit-testable without Docling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class PageTable:
    page_num: int
    rows: list[list[str]] = field(default_factory=list)


class TableExtractor(Protocol):
    """Produces (tables, full_text) from PDF bytes. Docling impl + test fakes."""

    def extract(self, data: bytes) -> tuple[list[PageTable], str]: ...
