"""Kafka producer base class — wraps confluent-kafka with JSON serialisation."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, date
from typing import Any

from confluent_kafka import Producer, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

logger = logging.getLogger(__name__)


class _DatetimeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


def _build_conf() -> dict[str, Any]:
    conf: dict[str, Any] = {
        "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
        "acks": "all",
        "retries": 5,
        "retry.backoff.ms": 300,
        "enable.idempotence": True,
        "compression.type": "lz4",
        "linger.ms": 5,
        "batch.size": 65536,
    }
    # Confluent Cloud auth (set in prod, skipped locally)
    api_key = os.environ.get("KAFKA_API_KEY")
    api_secret = os.environ.get("KAFKA_API_SECRET")
    if api_key and api_secret:
        conf.update(
            {
                "security.protocol": "SASL_SSL",
                "sasl.mechanisms": "PLAIN",
                "sasl.username": api_key,
                "sasl.password": api_secret,
            }
        )
    return conf


class KafkaProducerClient:
    """Thread-safe producer.  Instantiate once per process."""

    def __init__(self) -> None:
        self._producer = Producer(_build_conf())
        logger.info("Kafka producer initialised")

    def produce(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Serialise value as JSON and enqueue for delivery."""
        payload = json.dumps(value, cls=_DatetimeEncoder).encode()
        encoded_key = key.encode() if key else None
        self._producer.produce(
            topic=topic,
            value=payload,
            key=encoded_key,
            headers=headers or {},
            on_delivery=self._delivery_callback,
        )
        # poll to trigger delivery callbacks (non-blocking)
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> None:
        """Block until all outstanding messages are delivered."""
        remaining = self._producer.flush(timeout)
        if remaining > 0:
            logger.warning("%d message(s) not delivered within %.1fs", remaining, timeout)

    def close(self) -> None:
        self.flush()

    @staticmethod
    def _delivery_callback(err: Any, msg: Any) -> None:
        if err:
            logger.error(
                "Delivery failed for topic=%s key=%s: %s",
                msg.topic(), msg.key(), err,
            )
        else:
            logger.debug(
                "Delivered to %s [%d] offset=%d",
                msg.topic(), msg.partition(), msg.offset(),
            )
