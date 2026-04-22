"""Aggregator Service — joins the three AI pipeline results and writes to Postgres.

Consumer group: aggregator-group
Input topic:    processed-news
Output topic:   new-articles-pub (WebSocket broadcast)

Join logic:
  - Each AI service publishes a message with field = summary | geo_category | translations
  - Aggregator accumulates partial results in Redis (HSET partial:{article_id})
  - Increments Redis join counter (INCR join:{article_id})
  - When counter reaches 3 → all three results arrived → write to Postgres
  - Publishes to new-articles-pub for real-time WebSocket broadcast
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

from base_service import AsyncBaseKafkaService
from cache.client import close_redis, get_redis
from cache.helpers import (
    delete_join_counter,
    delete_partial_results,
    get_all_partial_results,
    increment_join_counter,
    store_partial_result,
)
from db.connection import get_pool
from db.queries import ArticleQueries, EngagementQueries, TranslationQueries
from models.article import NewArticlePub, ProcessedField

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

NEW_ARTICLES_TOPIC = "new-articles-pub"
REQUIRED_FIELDS = 3  # summary + geo_category + translations


class AggregatorService(AsyncBaseKafkaService):
    """Joins 3 AI results via Redis counter, writes to Postgres, broadcasts via Kafka."""

    group_id = "aggregator-group"
    input_topics = ["processed-news"]

    # ── Core logic ────────────────────────────────────────────────────────────

    async def process(self, msg: dict[str, Any]) -> None:
        article_id_str = msg.get("article_id", "")
        field = msg.get("field")
        data = msg.get("data", {})

        if not article_id_str or not field:
            self._logger.warning("Malformed processed-news message: %s", msg)
            return

        article_id = uuid.UUID(article_id_str)

        # Accumulate partial result in Redis
        await store_partial_result(article_id_str, field, data)
        count = await increment_join_counter(article_id_str)
        self._logger.debug("Join counter %s: %d/%d", article_id_str, count, REQUIRED_FIELDS)

        if count < REQUIRED_FIELDS:
            return  # waiting for remaining AI results

        # All three results arrived
        partials = await get_all_partial_results(article_id_str)
        if len(partials) < REQUIRED_FIELDS:
            self._logger.warning(
                "Counter=%d but only %d partial results in Redis for %s — waiting",
                count, len(partials), article_id_str,
            )
            return

        try:
            await self._flush_to_postgres(article_id, partials)
            await self._publish_to_websocket(article_id, partials)
        finally:
            # Clean up Redis state regardless of outcome
            await delete_join_counter(article_id_str)
            await delete_partial_results(article_id_str)

    async def async_cleanup(self) -> None:
        """Close Redis and Postgres pools on shutdown."""
        await close_redis()

    # ── Private: Postgres write ───────────────────────────────────────────────

    async def _flush_to_postgres(
        self,
        article_id: uuid.UUID,
        partials: dict[str, Any],
    ) -> None:
        summary_data = partials.get(ProcessedField.SUMMARY.value, {})
        geo_data = partials.get(ProcessedField.GEO_CATEGORY.value, {})
        trans_data = partials.get(ProcessedField.TRANSLATIONS.value, {})

        published_at_raw = geo_data.get("published_at")
        try:
            published_at = datetime.fromisoformat(
                str(published_at_raw).rstrip("Z")
            ).replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            published_at = datetime.now(timezone.utc)

        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await ArticleQueries.insert(conn, {
                    "article_id": article_id,
                    "source": geo_data.get("source", "newsapi"),
                    "original_url": geo_data.get("original_url"),
                    "title": geo_data.get("title", ""),
                    "body": geo_data.get("body"),
                    "image_url": geo_data.get("image_url"),
                    "author": geo_data.get("author"),
                    "published_at": published_at,
                    "status": "pending",
                    "language": geo_data.get("language", "en"),
                })

                await ArticleQueries.update_processed(conn, {
                    "article_id": article_id,
                    "category": geo_data.get("category"),
                    "geo_place_name": geo_data.get("geo_place_name"),
                    "lat": geo_data.get("lat"),
                    "lng": geo_data.get("lng"),
                })

                if summary_data.get("summary"):
                    await TranslationQueries.upsert(
                        conn,
                        article_id=article_id,
                        language_code="summary",
                        title=None,
                        summary=summary_data["summary"],
                    )

                for entry in trans_data.get("translations", []):
                    await TranslationQueries.upsert(
                        conn,
                        article_id=article_id,
                        language_code=entry["language_code"],
                        title=entry.get("title"),
                        summary=entry.get("summary"),
                    )

                await EngagementQueries.upsert_engagement(conn, article_id)

        self._logger.info("Flushed article_id=%s to Postgres", article_id)

    # ── Private: WebSocket broadcast ──────────────────────────────────────────

    async def _publish_to_websocket(
        self,
        article_id: uuid.UUID,
        partials: dict[str, Any],
    ) -> None:
        geo_data = partials.get(ProcessedField.GEO_CATEGORY.value, {})
        lat = geo_data.get("lat")
        lng = geo_data.get("lng")

        if lat is None or lng is None:
            self._logger.debug(
                "Skipping WS pub for article_id=%s — no coordinates", article_id
            )
            return

        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT title, image_url FROM articles WHERE article_id = $1", article_id
            )

        if not row:
            return

        pub = NewArticlePub(
            article_id=article_id,
            lat=lat,
            lng=lng,
            category=geo_data.get("category", "General"),
            title=row["title"],
            image_url=row["image_url"],
        )
        self._producer.produce(
            topic=NEW_ARTICLES_TOPIC,
            value=pub.model_dump(mode="json"),
            key=str(article_id),
        )


if __name__ == "__main__":
    AggregatorService().start()
