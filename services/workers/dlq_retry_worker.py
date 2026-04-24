"""DLQ Retry Worker — retries failed articles from the failed-news Kafka topic.

Consumes from failed-news (DLQ), re-publishes to raw-news with exponential backoff.
After 5 total retries marks article status as 'failed' in Postgres.

Retry count is stored in the message payload under _dlq_retry_count.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

sys.path.insert(0, "/app/shared")

from db.connection import close_pool, get_conn, get_pool
from db.queries import ArticleQueries
from kafka.consumer import KafkaConsumerClient
from kafka.producer import KafkaProducerClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("dlq-retry-worker")

CONSUMER_GROUP = "dlq-retry-group"
RAW_NEWS_TOPIC = "raw-news"
MAX_RETRIES = 5


def compute_backoff(retry_count: int) -> float:
    """Exponential backoff: 2^retry_count seconds, capped at 300s."""
    return min(300.0, 2 ** retry_count)


async def mark_failed(article_id_str: str) -> None:
    try:
        article_id = uuid.UUID(article_id_str)
        async with get_conn() as conn:
            await ArticleQueries.update_status(conn, article_id, "failed")
        logger.warning("Marked article_id=%s as failed", article_id_str)
    except Exception as exc:
        logger.error("Could not mark article failed: %s", exc)


def _start_health_server() -> None:
    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
        def log_message(self, *a): pass
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=HTTPServer(("", port), _H).serve_forever, daemon=True).start()


def main() -> None:
    _start_health_server()
    producer = KafkaProducerClient()
    consumer = KafkaConsumerClient(
        topics=["failed-news"],
        group_id=CONSUMER_GROUP,
        dlq_producer=producer,  # self-referential but avoids infinite DLQ loops
    )

    running = True

    def _shutdown(sig: int, _: Any) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(get_pool())

    logger.info("DLQ retry worker started")

    while running:
        msg = consumer.poll_one(timeout=1.0)
        if msg is None:
            continue

        value = msg["value"]
        article_id = value.get("article_id", "unknown")
        retry_count = int(value.get("_dlq_retry_count", 0))

        if retry_count >= MAX_RETRIES:
            logger.warning(
                "article_id=%s exhausted %d retries — marking as failed",
                article_id, MAX_RETRIES,
            )
            loop.run_until_complete(mark_failed(article_id))
            consumer.commit(msg)
            continue

        backoff = compute_backoff(retry_count)
        logger.info(
            "Retrying article_id=%s (attempt %d/%d) after %.0fs",
            article_id, retry_count + 1, MAX_RETRIES, backoff,
        )
        time.sleep(backoff)

        # Increment retry counter and re-publish to raw-news
        value["_dlq_retry_count"] = retry_count + 1
        value.pop("_dlq_error", None)      # clear error info before re-process
        value.pop("_dlq_timestamp", None)

        producer.produce(
            topic=RAW_NEWS_TOPIC,
            value=value,
            key=str(article_id),
        )
        consumer.commit(msg)

    consumer.close()
    producer.flush()
    loop.run_until_complete(close_pool())
    loop.close()
    logger.info("DLQ retry worker stopped")


if __name__ == "__main__":
    main()
