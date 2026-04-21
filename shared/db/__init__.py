"""Shared database module — asyncpg pool management."""

from .connection import get_pool, close_pool, get_conn
from .queries import ArticleQueries, EngagementQueries, UserQueries

__all__ = [
    "get_pool",
    "close_pool",
    "get_conn",
    "ArticleQueries",
    "EngagementQueries",
    "UserQueries",
]
