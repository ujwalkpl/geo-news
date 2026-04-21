"""Base Kafka service classes — shared lifecycle for all consumer-producer services.

Usage::

    class SummarizerService(BaseKafkaService):
        group_id     = "summarizer-group"
        input_topics = ["raw-news"]
        output_topic = "processed-news"

        def process(self, msg: dict) -> dict:
            ...

    if __name__ == "__main__":
        SummarizerService().start()
"""

from __future__ import annotations

import asyncio
import logging
import signal
from abc import ABC, abstractmethod
from typing import Any

from kafka.consumer import KafkaConsumerClient
from kafka.producer import KafkaProducerClient


# ── Synchronous base ──────────────────────────────────────────────────────────

class BaseKafkaService(ABC):
    """Base for synchronous Kafka consumer-producer services.

    Subclasses declare three class-level config attributes and implement
    process(). Everything else — poll loop, signal handling, DLQ routing,
    commit, and graceful shutdown — is handled here once.

    Class attributes to define in subclass:
        group_id     (str)       Kafka consumer group ID.
        input_topics (list[str]) Topics to subscribe to.
        output_topic (str)       Topic to publish results to.
    """

    group_id: str
    input_topics: list[str]
    output_topic: str

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._producer = KafkaProducerClient()
        self._consumer = KafkaConsumerClient(
            topics=self.input_topics,
            group_id=self.group_id,
            dlq_producer=self._producer,
        )
        self._running = False

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def process(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Process a single message and return the result to publish.

        Raise any exception to trigger on_error().
        """

    def on_error(self, msg: dict[str, Any], exc: Exception) -> dict[str, Any] | None:
        """Handle a processing failure.

        Returns:
            dict  — publish as fallback result (keeps join counter working).
            None  — send to DLQ instead (default behaviour).

        Override in subclasses where a fallback result is preferable to DLQ.
        """
        self._logger.error(
            "Processing failed for article_id=%s: %s",
            msg.get("article_id", "unknown"), exc,
        )
        return None  # → DLQ by default

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the blocking poll loop. Returns after SIGTERM / SIGINT."""
        self._running = True
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        self._logger.info("%s started", self.__class__.__name__)

        while self._running:
            msg = self._consumer.poll_one(timeout=1.0)
            if msg is None:
                continue
            self._dispatch(msg)

        self._shutdown()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _dispatch(self, msg: dict[str, Any]) -> None:
        """Route a polled message through process() with error handling."""
        article_id = msg["value"].get("article_id", "unknown")
        try:
            result = self.process(msg["value"])
            self._producer.produce(
                topic=self.output_topic,
                value=result,
                key=str(article_id),
            )
            self._consumer.commit(msg)
            self._logger.info("Processed article_id=%s", article_id)
        except Exception as exc:
            fallback = self.on_error(msg["value"], exc)
            if fallback is not None:
                self._producer.produce(
                    topic=self.output_topic,
                    value=fallback,
                    key=str(article_id),
                )
            else:
                self._consumer.send_to_dlq(msg["value"], str(exc))
            self._consumer.commit(msg)

    def _shutdown(self) -> None:
        self._consumer.close()
        self._producer.flush()
        self._logger.info("%s stopped", self.__class__.__name__)

    def _handle_shutdown(self, sig: int, _: Any) -> None:
        self._logger.info("Shutdown signal received (%d)", sig)
        self._running = False


# ── Async base ────────────────────────────────────────────────────────────────

class AsyncBaseKafkaService(ABC):
    """Base for async Kafka consumer services (e.g. those writing to Postgres/Redis).

    process() is async and is responsible for its own output publishing,
    since async services often write to multiple sinks (DB + Kafka).

    Class attributes to define in subclass:
        group_id     (str)       Kafka consumer group ID.
        input_topics (list[str]) Topics to subscribe to.
    """

    group_id: str
    input_topics: list[str]

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._producer = KafkaProducerClient()
        self._consumer = KafkaConsumerClient(
            topics=self.input_topics,
            group_id=self.group_id,
            dlq_producer=self._producer,
        )
        self._running = False
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    async def process(self, msg: dict[str, Any]) -> None:
        """Process a single message asynchronously.

        Responsible for writing results to any sinks (Postgres, Kafka, Redis).
        Raise any exception to trigger on_error().
        """

    async def on_error(self, msg: dict[str, Any], exc: Exception) -> None:
        """Handle a processing failure. Default: send to DLQ."""
        self._logger.error(
            "Processing failed for article_id=%s: %s",
            msg.get("article_id", "unknown"), exc,
        )
        self._consumer.send_to_dlq(msg, str(exc))

    async def async_cleanup(self) -> None:
        """Override to add async teardown logic (e.g. close Redis / Postgres pools)."""

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the blocking poll loop. Returns after SIGTERM / SIGINT."""
        self._running = True
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        self._logger.info("%s started", self.__class__.__name__)

        while self._running:
            msg = self._consumer.poll_one(timeout=1.0)
            if msg is None:
                continue
            self._dispatch(msg)

        self._shutdown()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _dispatch(self, msg: dict[str, Any]) -> None:
        article_id = msg["value"].get("article_id", "unknown")
        try:
            self._loop.run_until_complete(self.process(msg["value"]))
            self._consumer.commit(msg)
        except Exception as exc:
            self._loop.run_until_complete(self.on_error(msg["value"], exc))
            self._consumer.commit(msg)

    def _shutdown(self) -> None:
        self._consumer.close()
        self._producer.flush()
        self._loop.run_until_complete(self.async_cleanup())
        self._loop.close()
        self._logger.info("%s stopped", self.__class__.__name__)

    def _handle_shutdown(self, sig: int, _: Any) -> None:
        self._logger.info("Shutdown signal received (%d)", sig)
        self._running = False
