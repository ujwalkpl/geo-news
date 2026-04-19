"""Heatmap Refresh Worker — refreshes the heatmap_points materialized view.

Triggered every 5 minutes via Cloud Scheduler (HTTP POST /run).
"""

from __future__ import annotations

import asyncio
import logging
import sys

from fastapi import FastAPI

sys.path.insert(0, "/app/shared")

from db.connection import close_pool, get_conn, get_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("heatmap-worker")

app = FastAPI(title="GeoNews Heatmap Refresh Worker")


async def run_refresh() -> dict:
    async with get_conn() as conn:
        await conn.execute(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY heatmap_points"
        )
    logger.info("Heatmap materialized view refreshed")
    return {"refreshed": True}


@app.post("/run")
async def trigger_run() -> dict:
    result = await run_refresh()
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
    asyncio.run(run_refresh())
