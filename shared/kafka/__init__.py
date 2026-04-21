"""Shared Kafka module — producer and consumer base classes."""

from .producer import KafkaProducerClient
from .consumer import KafkaConsumerClient

__all__ = ["KafkaProducerClient", "KafkaConsumerClient"]
