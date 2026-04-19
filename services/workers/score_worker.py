"""Score Worker — recomputes time-decay scores for recent articles.

Triggered every 5 minutes via Cloud Scheduler (HTTP POST /run).
Also runnable standalone: python score_worker.py

Formula: score = (likes - dislikes) / (age_in_hours + 2)^1.8
"""

from __future__ import annotations

import asyncio
import logging
import sys

import uvicorn
from fastapi import FastAPI

sys.path.insert(0, "/app/shared")

from db.connection import close_pool, get_conn, get_pool
from db.queries import ArticleQueries, EngagementQueries
from cache.helpers import update_popular_score

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("score-worker")

app = FastAPI(title="GeoNews Score Worker")


def compute_score(likes: int, dislikes: int, age_hours: float) -> float:
    return (likes - dislikes) / ((age_hours + 2.0) ** 1.8)


async def run_score_update() -> dict:
    async with get_conn() as conn:
        rows = await ArticleQueries.get_articles_for_score_update(conn, hours=48)

    if not rows:
        return {"updated": 0}

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    updates: list[tuple[float, object]] = []
    redis_updates: list[tuple[str, float, str | None]] = []

    for row in rows:
        age_hours = (now - row["published_at"].replace(tzinfo=timezone.utc)).total_seconds() / 3600
        score = compute_score(row["likes"], row["dislikes"], age_hours)
        updates.append((score, row["article_id"]))

    async with get_conn() as conn:
        await EngagementQueries.bulk_update_scores(conn, updates)

    # Update Redis sorted sets
    for score, article_id in updates:
        await update_popular_score(str(article_id), score)

    logger.info("Score worker updated %d articles", len(updates))
    return {"updated": len(updates)}


@app.post("/run")
async def trigger_run() -> dict:
    result = await run_score_update()
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
    asyncio.run(run_score_update())
