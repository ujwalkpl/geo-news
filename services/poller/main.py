"""Event Registry Poller — fetches latest articles and publishes to Kafka raw-news.

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

EVENT_REGISTRY_URL = "https://eventregistry.org/api/v1/article/getArticles"

CATEGORIES: dict[str, str] = {
    "business":      "dmoz/Business",
    "technology":    "dmoz/Computers",
    "health":        "dmoz/Health",
    "science":       "dmoz/Science",
    "sports":        "dmoz/Sports",
    "entertainment": "dmoz/Arts",
    "general":       "dmoz/News",
}

_producer: KafkaProducerClient | None = None


def get_producer() -> KafkaProducerClient:
    global _producer
    if _producer is None:
        _producer = KafkaProducerClient()
    return _producer


async def fetch_category(
    client: httpx.AsyncClient,
    category: str,
    category_uri: str,
    api_key: str,
    page_size: int = 100,
) -> list[dict]:
    query = {
        "$query": {"categoryUri": category_uri},
        "$filter": {
            "forceMaxDataTimeWindow": "1",
            "lang": "eng",
            "isDuplicate": "skipDuplicates",
            "dataType": ["news"],
        },
    }
    params = {
        "query": json.dumps(query),
        "resultType": "articles",
        "articlesSortBy": "date",
        "articlesSortByAsc": "false",
        "articlesCount": page_size,
        "articleBodyLen": 500,
        "includeArticleImage": "true",
        "includeArticleAuthors": "true",
        "apiKey": api_key,
    }
    try:
        resp = await client.get(EVENT_REGISTRY_URL, params=params, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", {}).get("results", [])
    except httpx.HTTPStatusError as exc:
        logger.error("Event Registry HTTP %d for category=%s: %s",
                     exc.response.status_code, category, exc.response.text[:200])
        return []
    except Exception as exc:
        logger.error("Event Registry request failed for category=%s: %s", category, exc)
        return []


async def process_article(raw: dict, producer: KafkaProducerClient) -> bool:
    url = (raw.get("url") or "").strip()
    if not url:
        return False

    title = (raw.get("title") or "").strip()
    if not title:
        return False

    if await dedup_check(url):
        logger.debug("Duplicate skipped: %s", url)
        return False

    article_id = uuid.uuid4()

    published_at_str = raw.get("dateTimePub") or raw.get("dateTime") or datetime.now(timezone.utc).isoformat()
    try:
        published_at = datetime.fromisoformat(published_at_str.rstrip("Z")).replace(tzinfo=timezone.utc)
    except ValueError:
        published_at = datetime.now(timezone.utc)

    authors = raw.get("authors") or []
    author_str = ", ".join(a.get("name", "") for a in authors if a.get("name")) or None

    article = RawArticle(
        article_id=article_id,
        source=ArticleSource.NEWSAPI,
        original_url=url,
        title=title,
        body=raw.get("body") or "",
        image_url=raw.get("image"),
        author=author_str,
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
    api_key = os.environ["NEWSAPI_KEY"]   # Secret Manager secret name; value is Event Registry key
    producer = get_producer()
    published = 0
    skipped = 0

    async with httpx.AsyncClient() as client:
        tasks = [fetch_category(client, cat, uri, api_key) for cat, uri in CATEGORIES.items()]
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
    result = await run_poll()
    return {"status": "ok", **result}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    asyncio.run(run_poll())
