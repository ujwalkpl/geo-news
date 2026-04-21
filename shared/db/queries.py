"""Typed query helpers for all tables.

Each class exposes static / class methods that accept a connection so callers
can compose them inside transactions when needed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from asyncpg import Connection, Record


class ArticleQueries:
    """CRUD helpers for the articles table."""

    @staticmethod
    async def insert(conn: Connection, data: dict[str, Any]) -> None:
        """Insert a new article row.  data keys must match column names."""
        await conn.execute(
            """
            INSERT INTO articles (
                article_id, source, original_url, title, body,
                image_url, author, published_at, status, language
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10
            ) ON CONFLICT (article_id) DO NOTHING
            """,
            data["article_id"],
            data["source"],
            data.get("original_url"),
            data["title"],
            data.get("body"),
            data.get("image_url"),
            data.get("author"),
            data["published_at"],
            data.get("status", "pending"),
            data.get("language"),
        )

    @staticmethod
    async def update_processed(conn: Connection, data: dict[str, Any]) -> None:
        """Update article with AI-pipeline results and mark as processed."""
        await conn.execute(
            """
            UPDATE articles
            SET
                status         = 'processed',
                category       = $2,
                geo_place_name = $3,
                location       = ST_SetSRID(ST_MakePoint($4, $5), 4326)::geography
            WHERE article_id = $1
            """,
            data["article_id"],
            data.get("category"),
            data.get("geo_place_name"),
            data.get("lng"),   # ST_MakePoint(lng, lat)
            data.get("lat"),
        )

    @staticmethod
    async def update_status(
        conn: Connection,
        article_id: uuid.UUID,
        status: str,
    ) -> None:
        await conn.execute(
            "UPDATE articles SET status = $2 WHERE article_id = $1",
            article_id,
            status,
        )

    @staticmethod
    async def get_by_id(conn: Connection, article_id: uuid.UUID) -> Record | None:
        return await conn.fetchrow(
            """
            SELECT a.*, ae.likes, ae.dislikes, ae.view_count, ae.score
            FROM articles a
            LEFT JOIN article_engagement ae USING (article_id)
            WHERE a.article_id = $1
            """,
            article_id,
        )

    @staticmethod
    async def get_in_bbox(
        conn: Connection,
        sw_lat: float,
        sw_lng: float,
        ne_lat: float,
        ne_lng: float,
        category: str | None = None,
        limit: int = 200,
    ) -> list[Record]:
        """ST_Within bounding-box query using PostGIS geography column."""
        if category and category.lower() != "all":
            return await conn.fetch(
                """
                SELECT a.article_id, a.title, a.category, a.published_at,
                       ST_Y(location::geometry) AS lat,
                       ST_X(location::geometry) AS lng,
                       ae.score
                FROM articles a
                LEFT JOIN article_engagement ae USING (article_id)
                WHERE
                    a.status = 'processed'
                    AND a.location IS NOT NULL
                    AND ST_Within(
                        a.location::geometry,
                        ST_MakeEnvelope($1, $2, $3, $4, 4326)
                    )
                    AND a.category = $5
                ORDER BY ae.score DESC NULLS LAST
                LIMIT $6
                """,
                sw_lng, sw_lat, ne_lng, ne_lat, category, limit,
            )
        return await conn.fetch(
            """
            SELECT a.article_id, a.title, a.category, a.published_at,
                   ST_Y(location::geometry) AS lat,
                   ST_X(location::geometry) AS lng,
                   ae.score
            FROM articles a
            LEFT JOIN article_engagement ae USING (article_id)
            WHERE
                a.status = 'processed'
                AND a.location IS NOT NULL
                AND ST_Within(
                    a.location::geometry,
                    ST_MakeEnvelope($1, $2, $3, $4, 4326)
                )
            ORDER BY ae.score DESC NULLS LAST
            LIMIT $5
            """,
            sw_lng, sw_lat, ne_lng, ne_lat, limit,
        )

    @staticmethod
    async def get_heatmap(
        conn: Connection,
        sw_lat: float,
        sw_lng: float,
        ne_lat: float,
        ne_lng: float,
        category: str | None = None,
    ) -> list[Record]:
        """Query heatmap materialized view."""
        if category and category.lower() != "all":
            return await conn.fetch(
                """
                SELECT article_id,
                       ST_Y(location::geometry) AS lat,
                       ST_X(location::geometry) AS lng,
                       category, score
                FROM heatmap_points
                WHERE
                    ST_Within(
                        location::geometry,
                        ST_MakeEnvelope($1, $2, $3, $4, 4326)
                    )
                    AND category = $5
                """,
                sw_lng, sw_lat, ne_lng, ne_lat, category,
            )
        return await conn.fetch(
            """
            SELECT article_id,
                   ST_Y(location::geometry) AS lat,
                   ST_X(location::geometry) AS lng,
                   category, score
            FROM heatmap_points
            WHERE ST_Within(
                location::geometry,
                ST_MakeEnvelope($1, $2, $3, $4, 4326)
            )
            """,
            sw_lng, sw_lat, ne_lng, ne_lat,
        )

    @staticmethod
    async def get_feed(
        conn: Connection,
        category: str | None,
        page: int,
        page_size: int = 20,
        sort: str = "published_at",
    ) -> list[Record]:
        offset = (page - 1) * page_size
        order = "ae.score DESC NULLS LAST" if sort == "popular" else "a.published_at DESC"

        if category and category.lower() != "all":
            return await conn.fetch(
                f"""
                SELECT a.article_id, a.title, a.image_url, a.category,
                       a.published_at, a.geo_place_name, a.language,
                       ae.likes, ae.score
                FROM articles a
                LEFT JOIN article_engagement ae USING (article_id)
                WHERE a.status = 'processed' AND a.category = $1
                ORDER BY {order}
                LIMIT $2 OFFSET $3
                """,
                category, page_size, offset,
            )
        return await conn.fetch(
            f"""
            SELECT a.article_id, a.title, a.image_url, a.category,
                   a.published_at, a.geo_place_name, a.language,
                   ae.likes, ae.score
            FROM articles a
            LEFT JOIN article_engagement ae USING (article_id)
            WHERE a.status = 'processed'
            ORDER BY {order}
            LIMIT $1 OFFSET $2
            """,
            page_size, offset,
        )

    @staticmethod
    async def get_articles_for_score_update(
        conn: Connection,
        hours: int = 48,
    ) -> list[Record]:
        """Fetch articles needing score recomputation."""
        return await conn.fetch(
            """
            SELECT a.article_id, a.published_at,
                   COALESCE(ae.likes, 0) AS likes,
                   COALESCE(ae.dislikes, 0) AS dislikes
            FROM articles a
            LEFT JOIN article_engagement ae USING (article_id)
            WHERE a.published_at > NOW() - ($1 || ' hours')::INTERVAL
              AND a.status = 'processed'
            """,
            str(hours),
        )


class EngagementQueries:
    """Helpers for article_engagement and user_reactions tables."""

    @staticmethod
    async def upsert_engagement(conn: Connection, article_id: uuid.UUID) -> None:
        await conn.execute(
            """
            INSERT INTO article_engagement (article_id)
            VALUES ($1)
            ON CONFLICT (article_id) DO NOTHING
            """,
            article_id,
        )

    @staticmethod
    async def bulk_update_counts(
        conn: Connection,
        deltas: list[tuple[uuid.UUID, int, int]],
    ) -> None:
        """Bulk apply (likes_delta, dislikes_delta) from Redis flush.

        Args:
            deltas: list of (article_id, likes_delta, dislikes_delta)
        """
        await conn.executemany(
            """
            INSERT INTO article_engagement (article_id, likes, dislikes, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (article_id) DO UPDATE SET
                likes      = article_engagement.likes + EXCLUDED.likes,
                dislikes   = article_engagement.dislikes + EXCLUDED.dislikes,
                updated_at = NOW()
            """,
            deltas,
        )

    @staticmethod
    async def update_score(
        conn: Connection,
        article_id: uuid.UUID,
        score: float,
    ) -> None:
        await conn.execute(
            """
            UPDATE article_engagement
            SET score = $2, updated_at = NOW()
            WHERE article_id = $1
            """,
            article_id,
            score,
        )

    @staticmethod
    async def bulk_update_scores(
        conn: Connection,
        scores: list[tuple[float, uuid.UUID]],
    ) -> None:
        await conn.executemany(
            """
            UPDATE article_engagement
            SET score = $1, updated_at = NOW()
            WHERE article_id = $2
            """,
            scores,
        )

    @staticmethod
    async def upsert_reaction(
        conn: Connection,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
        reaction: str,
    ) -> str:
        """Insert or change a reaction. Returns 'new' | 'changed' | 'exists'."""
        existing = await conn.fetchrow(
            "SELECT reaction FROM user_reactions WHERE user_id=$1 AND article_id=$2",
            user_id, article_id,
        )
        if existing is None:
            await conn.execute(
                """
                INSERT INTO user_reactions (user_id, article_id, reaction)
                VALUES ($1, $2, $3)
                """,
                user_id, article_id, reaction,
            )
            return "new"
        if existing["reaction"] == reaction:
            return "exists"
        await conn.execute(
            """
            UPDATE user_reactions SET reaction = $3
            WHERE user_id = $1 AND article_id = $2
            """,
            user_id, article_id, reaction,
        )
        return "changed"

    @staticmethod
    async def increment_view(conn: Connection, article_id: uuid.UUID) -> None:
        await conn.execute(
            """
            INSERT INTO article_engagement (article_id, view_count)
            VALUES ($1, 1)
            ON CONFLICT (article_id) DO UPDATE
                SET view_count = article_engagement.view_count + 1
            """,
            article_id,
        )


class UserQueries:
    """Helpers for the users table."""

    @staticmethod
    async def create(
        conn: Connection,
        user_id: uuid.UUID,
        email: str,
        username: str,
        password_hash: str,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO users (user_id, email, username, password_hash)
            VALUES ($1, $2, $3, $4)
            """,
            user_id, email, username, password_hash,
        )

    @staticmethod
    async def get_by_email(conn: Connection, email: str) -> Any | None:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1", email
        )

    @staticmethod
    async def get_by_id(conn: Connection, user_id: uuid.UUID) -> Any | None:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1", user_id
        )

    @staticmethod
    async def touch_last_seen(conn: Connection, user_id: uuid.UUID) -> None:
        await conn.execute(
            "UPDATE users SET last_seen = NOW() WHERE user_id = $1", user_id
        )


class TranslationQueries:
    """Helpers for article_translations table."""

    @staticmethod
    async def upsert(
        conn: Connection,
        article_id: uuid.UUID,
        language_code: str,
        title: str | None,
        summary: str | None,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO article_translations (article_id, language_code, title, summary)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (article_id, language_code) DO UPDATE SET
                title   = EXCLUDED.title,
                summary = EXCLUDED.summary
            """,
            article_id, language_code, title, summary,
        )

    @staticmethod
    async def get(
        conn: Connection,
        article_id: uuid.UUID,
        language_code: str,
    ) -> Any | None:
        return await conn.fetchrow(
            """
            SELECT * FROM article_translations
            WHERE article_id = $1 AND language_code = $2
            """,
            article_id, language_code,
        )
