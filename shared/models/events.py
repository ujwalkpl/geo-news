"""Pydantic models for Kafka event payloads."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class LikeEventType(str, Enum):
    LIKE = "like"
    DISLIKE = "dislike"
    UNLIKE = "unlike"
    UNDISLIKE = "undislike"


class LikeEvent(BaseModel):
    """Published to like-events Kafka topic."""
    event_id: uuid.UUID = uuid.uuid4()
    user_id: uuid.UUID
    article_id: uuid.UUID
    event_type: LikeEventType
    timestamp: datetime

    model_config = {"use_enum_values": True}
