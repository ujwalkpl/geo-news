"""Async Redis client — single shared connection pool."""

from __future__ import annotations

import logging
import os

import redis.asyncio as aioredis
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_redis: Redis | None = None


async def get_redis() -> Redis:
    """Return the global Redis client, creating it on first call."""
    global _redis
    if _redis is None:
        url = os.environ["REDIS_URL"]
        _redis = aioredis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        logger.info("Redis client initialised: %s", url)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("Redis client closed")
