"""NewsAPI Poller — fetches top headlines and publishes to Kafka raw-news.

Triggered every 5 minutes by Cloud Scheduler (HTTP POST to /poll).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI

import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

from kafka.producer import KafkaProducerClient
from cache.helpers import dedup_check, dedup_set
from models.article import RawArticle, ArticleSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("poller")

app = FastAPI(title="GeoNews Poller")

NEWSAPI_URL = "https://newsapi.org/v2/top-headlines"

# NewsAPI supports these categories directly
CATEGORIES = [
    "business",
    "entertainment",
    "general",
    "health",
    "science",
    "sports",
    "technology",
]

_producer: KafkaProducerClient | None = None


def get_producer() -> KafkaProducerClient:
    global _producer
    if _producer is None:
        _producer = KafkaProducerClient()
    return _producer


async def fetch_category(
    client: httpx.AsyncClient,
    category: str,
    api_key: str,
    page_size: int = 100,
) -> list[dict]:
    params = {
        "category": category,
        "language": "en",
        "pageSize": page_size,
        "apiKey": api_key,
    }
    try:
        resp = await client.get(NEWSAPI_URL, params=params, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", [])
    except httpx.HTTPStatusError as exc:
        logger.error("NewsAPI HTTP %d for category=%s", exc.response.status_code, category)
        return []
    except Exception as exc:
        logger.error("NewsAPI request failed for category=%s: %s", category, exc)
        return []


async def process_article(raw: dict, producer: KafkaProducerClient) -> bool:
    """Deduplicate and publish one article. Returns True if published."""
    url = (raw.get("url") or "").strip()
    # NewsAPI sometimes returns "[Removed]" as url
    if not url or url == "[Removed]":
        return False

    title = (raw.get("title") or "").strip()
    if not title or title == "[Removed]":
        return False

    if await dedup_check(url):
        logger.debug("Duplicate skipped: %s", url)
        return False

    article_id = uuid.uuid4()

    published_at_str = raw.get("publishedAt") or datetime.now(timezone.utc).isoformat()
    try:
        published_at = datetime.fromisoformat(published_at_str.rstrip("Z")).replace(tzinfo=timezone.utc)
    except ValueError:
        published_at = datetime.now(timezone.utc)

    source_name = (raw.get("source") or {}).get("name") or None
    author = raw.get("author") or source_name or None
    body = raw.get("content") or raw.get("description") or ""

    article = RawArticle(
        article_id=article_id,
        source=ArticleSource.NEWSAPI,
        original_url=url,
        title=title,
        body=body,
        image_url=raw.get("urlToImage"),
        author=author,
        published_at=published_at,
        language="en",
    )

    producer.produce(
        topic="raw-news",
        value=article.model_dump(mode="json"),
        key=str(article_id),
    )
    await dedup_set(url)
    return True


async def run_poll() -> dict:
    """Core polling logic — fetch all categories, publish new articles."""
    api_key = os.environ["NEWSAPI_KEY"]
    producer = get_producer()
    published = 0
    skipped = 0

    async with httpx.AsyncClient() as client:
        tasks = [fetch_category(client, cat, api_key) for cat in CATEGORIES]
        results = await asyncio.gather(*tasks)

    for articles in results:
        for raw in articles:
            ok = await process_article(raw, producer)
            if ok:
                published += 1
            else:
                skipped += 1

    producer.flush()
    logger.info("Poll complete: published=%d skipped=%d", published, skipped)
    return {"published": published, "skipped": skipped}


@app.post("/poll")
async def trigger_poll() -> dict:
    """Cloud Scheduler HTTP trigger endpoint."""
    result = await run_poll()
    return {"status": "ok", **result}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    asyncio.run(run_poll())
