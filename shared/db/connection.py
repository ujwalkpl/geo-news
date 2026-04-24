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
    """Return the global asyncpg pool, initialising it on first call.

    Pool sizes are intentionally small — Cloud SQL db-f1-micro caps at ~25
    total connections across all services. Override via env vars:
      DB_POOL_MIN  (default 1)
      DB_POOL_MAX  (default 3)
    Set DB_POOL_MAX=10 on the API service which needs higher concurrency.
    """
    global _pool
    if _pool is None:
        dsn = os.environ["POSTGRES_URL"]
        min_size = int(os.environ.get("DB_POOL_MIN", "1"))
        max_size = int(os.environ.get("DB_POOL_MAX", "3"))
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=min_size,
            max_size=max_size,
            max_inactive_connection_lifetime=300,
            command_timeout=30,
            statement_cache_size=0,   # disabled — saves memory on small instances
        )
        logger.info("asyncpg pool created (min=%d, max=%d)", min_size, max_size)
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
