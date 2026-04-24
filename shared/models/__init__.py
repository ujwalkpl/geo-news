"""Shared Pydantic models used across all services."""

from .article import (
    RawArticle,
    ProcessedArticle,
    ArticleStub,
    ArticleDetail,
    ArticleTranslation,
    ArticleEngagement,
    NewArticlePub,
    ProcessedField,
)
from .events import LikeEvent, LikeEventType

# User models are NOT imported here — they require pydantic[email] (email-validator).
# Import them directly where needed: from models.user import UserCreate, ...

__all__ = [
    "RawArticle",
    "ProcessedArticle",
    "ArticleStub",
    "ArticleDetail",
    "ArticleTranslation",
    "ArticleEngagement",
    "NewArticlePub",
    "ProcessedField",
    "LikeEvent",
    "LikeEventType",
]
