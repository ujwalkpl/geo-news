"""Shared Redis module — async client and helpers."""

from .client import get_redis, close_redis
from .helpers import (
    dedup_check,
    dedup_set,
    like_idempotency_check,
    like_idempotency_set,
    increment_like,
    increment_dislike,
    get_like_counts,
    reset_like_delta,
    set_join_counter,
    increment_join_counter,
    get_join_counter,
    set_cache,
    get_cache,
    invalidate_cache,
    blacklist_jwt,
    is_jwt_blacklisted,
)

__all__ = [
    "get_redis",
    "close_redis",
    "dedup_check",
    "dedup_set",
    "like_idempotency_check",
    "like_idempotency_set",
    "increment_like",
    "increment_dislike",
    "get_like_counts",
    "reset_like_delta",
    "set_join_counter",
    "increment_join_counter",
    "get_join_counter",
    "set_cache",
    "get_cache",
    "invalidate_cache",
    "blacklist_jwt",
    "is_jwt_blacklisted",
]
