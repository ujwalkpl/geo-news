"""Kafka consumer base class — handles polling, deserialization, DLQ, retries."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable, Awaitable

from confluent_kafka import Consumer, KafkaError, KafkaException, Message, Producer

from .producer import KafkaProducerClient, _build_conf

logger = logging.getLogger(__name__)

_DLQ_TOPIC = "failed-news"
_MAX_RETRIES = 3


def _build_consumer_conf(group_id: str) -> dict[str, Any]:
    conf: dict[str, Any] = {
        "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,     # manual commit after processing
        "max.poll.interval.ms": 300_000,
        "session.timeout.ms": 30_000,
        "fetch.min.bytes": 1,
        "fetch.wait.max.ms": 500,
    }
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


class KafkaConsumerClient:
    """
    Opinionated consumer wrapper.

    Usage::

        consumer = KafkaConsumerClient(
            topics=["raw-news"],
            group_id="summarizer-group",
        )

        async for message in consumer.messages():
            await handle(message)
    """

    def __init__(
        self,
        topics: list[str],
        group_id: str,
        dlq_producer: KafkaProducerClient | None = None,
    ) -> None:
        self._consumer = Consumer(_build_consumer_conf(group_id))
        self._consumer.subscribe(topics)
        self._dlq = dlq_producer or KafkaProducerClient()
        self._topics = topics
        self._group_id = group_id
        logger.info("Kafka consumer started: group=%s topics=%s", group_id, topics)

    def poll_one(self, timeout: float = 1.0) -> dict[str, Any] | None:
        """Poll for a single message, return parsed dict or None on timeout."""
        msg: Message | None = self._consumer.poll(timeout)
        if msg is None:
            return None
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return None
            raise KafkaException(msg.error())
        return {
            "value": json.loads(msg.value().decode()),
            "key": msg.key().decode() if msg.key() else None,
            "topic": msg.topic(),
            "partition": msg.partition(),
            "offset": msg.offset(),
            "_msg": msg,  # keep raw message for commit
        }

    def commit(self, msg_dict: dict[str, Any]) -> None:
        """Commit offset for the given message dict (after successful processing)."""
        self._consumer.commit(message=msg_dict["_msg"], asynchronous=False)

    def send_to_dlq(self, value: dict[str, Any], error: str) -> None:
        """Send a failed message to the dead-letter queue."""
        value["_dlq_error"] = error
        value["_dlq_timestamp"] = time.time()
        self._dlq.produce(topic=_DLQ_TOPIC, value=value)
        logger.warning("Message sent to DLQ: %s", error)

    def close(self) -> None:
        self._consumer.close()
        logger.info("Kafka consumer closed: group=%s", self._group_id)

    def __enter__(self) -> "KafkaConsumerClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
