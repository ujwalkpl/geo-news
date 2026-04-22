"""GeoNews REST API — FastAPI application entrypoint."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
sys.path.insert(0, os.path.dirname(__file__))

from db.connection import close_pool, get_pool
from cache.client import close_redis, get_redis

from routers import auth, news, search, users

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("api")

app = FastAPI(
    title="GeoNews API",
    version="1.0.0",
    description="Event-driven geospatial news aggregator API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(news.router, prefix="/news", tags=["news"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(users.router, prefix="/users", tags=["users"])


@app.on_event("startup")
async def startup() -> None:
    await get_pool()
    await get_redis()
    logger.info("API started")


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_pool()
    await close_redis()
    logger.info("API stopped")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
