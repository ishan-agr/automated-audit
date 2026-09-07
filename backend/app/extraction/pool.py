"""Bounded extraction job pool (job pooling).

Caps concurrent extractions with a semaphore so many uploads don't thrash CPU —
the local analogue of the KB engine's converter pool + worker replicas. `inline`
mode awaits jobs in-request (deterministic for tests / simple local runs); async
mode schedules them on the event loop and returns immediately.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.core.config import get_settings


class ExtractionPool:
    def __init__(self, max_concurrency: int, inline: bool) -> None:
        self._sem = asyncio.Semaphore(max(1, max_concurrency))
        self.inline = inline
        self._tasks: set[asyncio.Task] = set()

    async def _guarded(self, job: Callable[[], Awaitable[None]]) -> None:
        async with self._sem:
            await job()

    async def submit(self, job: Callable[[], Awaitable[None]]) -> asyncio.Task | None:
        """Schedule (async) or run (inline) a job. Returns the task in async mode."""
        if self.inline:
            await self._guarded(job)
            return None
        task = asyncio.create_task(self._guarded(job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def drain(self) -> None:
        """Await all in-flight tasks (test/shutdown helper)."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)


_pool: ExtractionPool | None = None


def get_pool() -> ExtractionPool:
    global _pool
    if _pool is None:
        s = get_settings()
        _pool = ExtractionPool(s.max_extract_concurrency, s.inline_jobs)
    return _pool
