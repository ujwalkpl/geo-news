"""Pydantic models for article data flow across the pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ArticleSource(str, Enum):
    NEWSAPI = "newsapi"
    USER_UPLOAD = "user_upload"


class ArticleStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class ArticleCategory(str, Enum):
    SPORTS = "Sports"
    AI = "AI"
    TECHNOLOGY = "Technology"
    POLITICS = "Politics"
    FINANCE = "Finance"
    HEALTH = "Health"
    ENTERTAINMENT = "Entertainment"
    GENERAL = "General"


class ProcessedField(str, Enum):
    """Tracks which AI pipeline result has arrived for the aggregator join."""
    SUMMARY = "summary"
    GEO_CATEGORY = "geo_category"
    TRANSLATIONS = "translations"


# ── Ingestion ─────────────────────────────────────────────────────────────────

class RawArticle(BaseModel):
    """Published to raw-news Kafka topic by Poller and Upload services."""
    article_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source: ArticleSource
    original_url: str | None = None
    title: str
    body: str | None = None
    image_url: str | None = None
    author: str | None = None
    published_at: datetime
    language: str | None = None
    # user-upload specific
    lat: float | None = None
    lng: float | None = None
    user_id: str | None = None
    is_user_upload: bool = False   # signals pipeline: skip summarization + geocoding

    model_config = {"use_enum_values": True}


# ── AI pipeline results ───────────────────────────────────────────────────────

class SummaryResult(BaseModel):
    article_id: uuid.UUID
    field: ProcessedField = ProcessedField.SUMMARY
    summary: str


class GeoCategoryResult(BaseModel):
    article_id: uuid.UUID
    field: ProcessedField = ProcessedField.GEO_CATEGORY
    category: str
    lat: float | None = None
    lng: float | None = None
    geo_place_name: str | None = None


class TranslationEntry(BaseModel):
    language_code: str
    title: str | None
    summary: str | None


class TranslationsResult(BaseModel):
    article_id: uuid.UUID
    field: ProcessedField = ProcessedField.TRANSLATIONS
    translations: list[TranslationEntry] = Field(default_factory=list)


# Generic processed-news envelope published by each AI service
class ProcessedArticleEnvelope(BaseModel):
    article_id: uuid.UUID
    field: ProcessedField
    data: dict[str, Any]

    model_config = {"use_enum_values": True}


# ── Aggregated / stored ───────────────────────────────────────────────────────

class ArticleTranslation(BaseModel):
    language_code: str
    title: str | None
    summary: str | None


class ArticleEngagement(BaseModel):
    article_id: uuid.UUID
    likes: int = 0
    dislikes: int = 0
    view_count: int = 0
    score: float = 0.0


class ArticleStub(BaseModel):
    """Lightweight projection for map pins and cluster items."""
    article_id: uuid.UUID
    title: str
    category: str | None
    published_at: datetime
    lat: float | None
    lng: float | None
    score: float = 0.0
    image_url: str | None = None


class ArticleDetail(BaseModel):
    """Full article detail returned by GET /news/:id."""
    article_id: uuid.UUID
    source: str
    title: str
    body: str | None
    image_url: str | None
    author: str | None
    published_at: datetime
    category: str | None
    geo_place_name: str | None
    lat: float | None
    lng: float | None
    language: str | None
    summary: str | None = None
    translations: list[ArticleTranslation] = Field(default_factory=list)
    engagement: ArticleEngagement | None = None


class ProcessedArticle(BaseModel):
    """Fully enriched article ready for Postgres write."""
    article_id: uuid.UUID
    source: str
    original_url: str | None
    title: str
    body: str | None
    image_url: str | None
    author: str | None
    published_at: datetime
    language: str | None
    # From classifier
    category: str | None
    lat: float | None
    lng: float | None
    geo_place_name: str | None
    # From summarizer
    summary: str | None
    # From translator
    translations: list[ArticleTranslation] = Field(default_factory=list)


# ── Real-time pub ─────────────────────────────────────────────────────────────

class NewArticlePub(BaseModel):
    """Published to new-articles-pub Kafka topic for WebSocket broadcast."""
    article_id: uuid.UUID
    lat: float
    lng: float
    category: str
    title: str
    score: float = 0.0
    image_url: str | None = None
