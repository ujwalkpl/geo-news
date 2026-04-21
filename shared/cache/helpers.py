"""High-level Redis helpers implementing the GeoNews key schema."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from .client import get_redis

logger = logging.getLogger(__name__)

# ── TTLs ──────────────────────────────────────────────────────────────────────
DEDUP_TTL         = 172_800   # 48 h
BBOX_CACHE_TTL    = 180       # 3 min
ARTICLE_CACHE_TTL = 900       # 15 min
FEED_P1_CACHE_TTL = 120       # 2 min
FEED_PN_CACHE_TTL = 600       # 10 min
HEATMAP_CACHE_TTL = 300       # 5 min
JOIN_COUNTER_TTL  = 3_600     # 1 h


# ── Deduplication ─────────────────────────────────────────────────────────────

def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


async def dedup_check(url: str) -> bool:
    """Return True if URL has been seen in the last 48 h."""
    r = await get_redis()
    return bool(await r.exists(f"dedup:url:{_url_hash(url)}"))


async def dedup_set(url: str) -> None:
    """Mark URL as seen (48 h TTL)."""
    r = await get_redis()
    await r.set(f"dedup:url:{_url_hash(url)}", "1", ex=DEDUP_TTL)


# ── Like / dislike idempotency ────────────────────────────────────────────────

async def like_idempotency_check(user_id: str, article_id: str) -> str | None:
    """Return 'like'/'dislike' if user already reacted, else None."""
    r = await get_redis()
    if await r.sismember(f"user:likes:{user_id}", article_id):
        return "like"
    if await r.sismember(f"user:dislikes:{user_id}", article_id):
        return "dislike"
    return None


async def like_idempotency_set(
    user_id: str,
    article_id: str,
    reaction: str,
) -> None:
    r = await get_redis()
    if reaction == "like":
        await r.sadd(f"user:likes:{user_id}", article_id)
        await r.srem(f"user:dislikes:{user_id}", article_id)
    else:
        await r.sadd(f"user:dislikes:{user_id}", article_id)
        await r.srem(f"user:likes:{user_id}", article_id)


# ── Like / dislike counters (delta before flush to Postgres) ──────────────────

async def increment_like(article_id: str) -> None:
    r = await get_redis()
    await r.hincrby(f"likes:{article_id}", "likes", 1)


async def increment_dislike(article_id: str) -> None:
    r = await get_redis()
    await r.hincrby(f"likes:{article_id}", "dislikes", 1)


async def decrement_like(article_id: str) -> None:
    r = await get_redis()
    # hincrby with negative value acts as decrement
    await r.hincrby(f"likes:{article_id}", "likes", -1)


async def decrement_dislike(article_id: str) -> None:
    r = await get_redis()
    await r.hincrby(f"likes:{article_id}", "dislikes", -1)


async def get_like_counts(article_id: str) -> dict[str, int]:
    r = await get_redis()
    data = await r.hgetall(f"likes:{article_id}")
    return {
        "likes":    int(data.get("likes", 0)),
        "dislikes": int(data.get("dislikes", 0)),
    }


async def reset_like_delta(article_id: str) -> None:
    r = await get_redis()
    await r.delete(f"likes:{article_id}")


async def get_all_like_delta_keys() -> list[str]:
    """Return all article_ids that have pending like deltas."""
    r = await get_redis()
    keys = await r.keys("likes:*")
    return [k.removeprefix("likes:") for k in keys]


# ── Popular sorted sets ───────────────────────────────────────────────────────

async def update_popular_score(article_id: str, score: float, category: str | None = None) -> None:
    r = await get_redis()
    await r.zadd("popular:24h", {article_id: score})
    if category:
        await r.zadd(f"popular:24h:{category.lower()}", {article_id: score})


# ── Aggregator join counter ───────────────────────────────────────────────────

async def increment_join_counter(article_id: str) -> int:
    """Increment the join counter for article_id. Returns new value."""
    r = await get_redis()
    key = f"join:{article_id}"
    val = await r.incr(key)
    if val == 1:
        await r.expire(key, JOIN_COUNTER_TTL)
    return val


async def get_join_counter(article_id: str) -> int:
    r = await get_redis()
    val = await r.get(f"join:{article_id}")
    return int(val) if val else 0


async def set_join_counter(article_id: str, value: int) -> None:
    r = await get_redis()
    await r.set(f"join:{article_id}", value, ex=JOIN_COUNTER_TTL)


async def delete_join_counter(article_id: str) -> None:
    r = await get_redis()
    await r.delete(f"join:{article_id}")


# ── Partial result storage (for aggregator join) ──────────────────────────────

async def store_partial_result(article_id: str, field: str, data: dict) -> None:
    """Store a partial AI result keyed by article_id + field."""
    r = await get_redis()
    await r.hset(
        f"partial:{article_id}",
        field,
        json.dumps(data),
    )
    await r.expire(f"partial:{article_id}", JOIN_COUNTER_TTL)


async def get_all_partial_results(article_id: str) -> dict[str, dict]:
    r = await get_redis()
    raw = await r.hgetall(f"partial:{article_id}")
    return {k: json.loads(v) for k, v in raw.items()}


async def delete_partial_results(article_id: str) -> None:
    r = await get_redis()
    await r.delete(f"partial:{article_id}")


# ── Generic cache ─────────────────────────────────────────────────────────────

async def set_cache(key: str, value: Any, ttl: int) -> None:
    r = await get_redis()
    await r.set(key, json.dumps(value), ex=ttl)


async def get_cache(key: str) -> Any | None:
    r = await get_redis()
    raw = await r.get(key)
    return json.loads(raw) if raw else None


async def invalidate_cache(*keys: str) -> None:
    r = await get_redis()
    if keys:
        await r.delete(*keys)


# ── JWT blacklist ─────────────────────────────────────────────────────────────

async def blacklist_jwt(jti: str, remaining_ttl: int) -> None:
    r = await get_redis()
    await r.set(f"blacklist:jwt:{jti}", "1", ex=remaining_ttl)


async def is_jwt_blacklisted(jti: str) -> bool:
    r = await get_redis()
    return bool(await r.exists(f"blacklist:jwt:{jti}"))


# ── WebSocket session tracking ────────────────────────────────────────────────

async def set_ws_session(user_id: str, instance_id: str, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.set(f"ws:session:{user_id}", instance_id, ex=ttl)


async def get_ws_session(user_id: str) -> str | None:
    r = await get_redis()
    return await r.get(f"ws:session:{user_id}")


async def delete_ws_session(user_id: str) -> None:
    r = await get_redis()
    await r.delete(f"ws:session:{user_id}")
