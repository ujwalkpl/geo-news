"""asyncpg connection pool management."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from asyncpg import Connection, Pool

logger = logging.getLogger(__name__)

_pool: Pool | None = None


async def get_pool() -> Pool:
    """Return the global asyncpg pool, initialising it on first call."""
    global _pool
    if _pool is None:
        dsn = os.environ["POSTGRES_URL"]
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=2,
            max_size=20,
            max_inactive_connection_lifetime=300,
            command_timeout=30,
            statement_cache_size=100,
        )
        logger.info("asyncpg pool created (min=2, max=20)")
    return _pool


async def close_pool() -> None:
    """Gracefully close the pool on shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")


@asynccontextmanager
async def get_conn() -> AsyncGenerator[Connection, None]:
    """Async context manager that yields a connection from the pool."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
