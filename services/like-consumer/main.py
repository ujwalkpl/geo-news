"""Like Consumer — reads like-events from Kafka and updates Redis counters.

Consumer group: like-consumer-group
Input topic:    like-events
Writes to:      Redis (ZINCRBY, HINCRBY, SADD)

NOTE: Postgres persistence is handled by the separate Like Flush Worker (workers/).
      This service is responsible only for fast Redis writes.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

from kafka.consumer import KafkaConsumerClient
from kafka.producer import KafkaProducerClient
from models.events import LikeEventType
from cache.helpers import (
    decrement_dislike,
    decrement_like,
    increment_dislike,
    increment_like,
    like_idempotency_set,
)
from cache.client import close_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("like-consumer")

CONSUMER_GROUP = "like-consumer-group"


async def handle_like_event(event: dict[str, Any]) -> None:
    user_id = event["user_id"]
    article_id = event["article_id"]
    event_type = event["event_type"]

    if event_type == LikeEventType.LIKE.value:
        await increment_like(article_id)
        await like_idempotency_set(user_id, article_id, "like")
    elif event_type == LikeEventType.DISLIKE.value:
        await increment_dislike(article_id)
        await like_idempotency_set(user_id, article_id, "dislike")
    elif event_type == LikeEventType.UNLIKE.value:
        await decrement_like(article_id)
    elif event_type == LikeEventType.UNDISLIKE.value:
        await decrement_dislike(article_id)
    else:
        logger.warning("Unknown like event type: %s", event_type)


def _start_health_server() -> None:
    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
        def log_message(self, *a): pass
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=HTTPServer(("", port), _H).serve_forever, daemon=True).start()


def main() -> None:
    _start_health_server()
    producer = KafkaProducerClient()  # for DLQ
    consumer = KafkaConsumerClient(
        topics=["like-events"],
        group_id=CONSUMER_GROUP,
        dlq_producer=producer,
    )

    running = True

    def _shutdown(sig: int, _: Any) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    logger.info("Like consumer started")

    while running:
        msg = consumer.poll_one(timeout=1.0)
        if msg is None:
            continue

        article_id = msg["value"].get("article_id", "unknown")
        try:
            loop.run_until_complete(handle_like_event(msg["value"]))
            consumer.commit(msg)
            logger.debug("Processed like event for article_id=%s", article_id)
        except Exception as exc:
            logger.error("Failed to process like event article_id=%s: %s", article_id, exc)
            consumer.send_to_dlq(msg["value"], str(exc))
            consumer.commit(msg)

    consumer.close()
    producer.flush()
    loop.run_until_complete(close_redis())
    loop.close()
    logger.info("Like consumer stopped")


if __name__ == "__main__":
    main()
