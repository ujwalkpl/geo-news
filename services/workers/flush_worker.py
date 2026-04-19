"""Like Flush Worker — reads Redis like deltas and bulk-writes to Postgres.

Triggered every 30 seconds via Cloud Scheduler (HTTP POST /run).

Steps:
1. Scan Redis for all keys matching likes:*
2. HGETALL each key to read delta counts
3. Bulk UPDATE article_engagement in Postgres
4. Reset Redis counters (DELETE key)
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid

from fastapi import FastAPI
import uvicorn

sys.path.insert(0, "/app/shared")

from db.connection import close_pool, get_conn, get_pool
from db.queries import EngagementQueries
from cache.helpers import get_all_like_delta_keys, get_like_counts, reset_like_delta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("flush-worker")

app = FastAPI(title="GeoNews Like Flush Worker")


async def run_flush() -> dict:
    article_ids = await get_all_like_delta_keys()
    if not article_ids:
        return {"flushed": 0}

    deltas: list[tuple[uuid.UUID, int, int]] = []
    for article_id_str in article_ids:
        counts = await get_like_counts(article_id_str)
        likes_delta = counts["likes"]
        dislikes_delta = counts["dislikes"]

        if likes_delta == 0 and dislikes_delta == 0:
            await reset_like_delta(article_id_str)
            continue

        try:
            article_id = uuid.UUID(article_id_str)
        except ValueError:
            logger.warning("Invalid article_id in Redis: %s", article_id_str)
            continue

        deltas.append((article_id, likes_delta, dislikes_delta))

    if not deltas:
        return {"flushed": 0}

    async with get_conn() as conn:
        await EngagementQueries.bulk_update_counts(conn, deltas)

    # Reset Redis counters after successful Postgres write
    for article_id, _, _ in deltas:
        await reset_like_delta(str(article_id))

    logger.info("Flush worker wrote %d article engagement deltas to Postgres", len(deltas))
    return {"flushed": len(deltas)}


@app.post("/run")
async def trigger_run() -> dict:
    result = await run_flush()
    return {"status": "ok", **result}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
async def startup() -> None:
    await get_pool()


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_pool()


if __name__ == "__main__":
    asyncio.run(run_flush())
