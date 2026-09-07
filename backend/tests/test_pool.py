"""The bounded extraction pool caps concurrency (job pooling)."""

from __future__ import annotations

import asyncio

from app.extraction.pool import ExtractionPool


def test_pool_bounds_concurrency():
    max_c = 2
    pool = ExtractionPool(max_concurrency=max_c, inline=False)
    live = 0
    peak = 0

    async def job():
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        await asyncio.sleep(0.01)
        live -= 1

    async def run():
        for _ in range(8):
            await pool.submit(job)
        await pool.drain()

    asyncio.run(run())
    assert peak <= max_c


def test_inline_pool_runs_immediately():
    pool = ExtractionPool(max_concurrency=1, inline=True)
    ran = []

    async def job():
        ran.append(1)

    async def run():
        task = await pool.submit(job)
        assert task is None  # inline returns no task
        assert ran == [1]  # already executed

    asyncio.run(run())
