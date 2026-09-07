"""Extractor interface. The pypdf baseline runs here today; a Docling adapter
(reusing the magoneai KB converter pool + router) implements the same protocol
later without touching the pipeline.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExtractedPageData:
    page_num: int  # 1-based
    text: str


class Extractor(Protocol):
    def page_count(self, data: bytes) -> int: ...

    def iter_pages(self, data: bytes) -> Iterator[ExtractedPageData]:
        """Yield pages in order. Bytes must already be un-encrypted."""
        ...
