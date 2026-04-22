"""News router — map, heatmap, feed, article detail, likes."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

import sys
sys.path.insert(0, "/app/shared")

from db.connection import get_conn
from db.queries import ArticleQueries, EngagementQueries, TranslationQueries
from kafka.producer import KafkaProducerClient
from models.events import LikeEvent, LikeEventType
from cache.helpers import (
    ARTICLE_CACHE_TTL,
    BBOX_CACHE_TTL,
    FEED_P1_CACHE_TTL,
    FEED_PN_CACHE_TTL,
    HEATMAP_CACHE_TTL,
    get_cache,
    like_idempotency_check,
    set_cache,
)

from deps import CurrentUser, OptionalUser

router = APIRouter()
_producer: KafkaProducerClient | None = None


def get_producer() -> KafkaProducerClient:
    global _producer
    if _producer is None:
        _producer = KafkaProducerClient()
    return _producer


def _quantize(coord: float, decimals: int = 2) -> str:
    factor = 10 ** decimals
    return str(math.floor(coord * factor) / factor)


# ── GET /news/map ─────────────────────────────────────────────────────────────

@router.get("/map")
async def get_map(
    bbox: str = Query(..., description="swLat,swLng,neLat,neLng"),
    category: str = Query("all"),
    lang: str = Query("en"),
) -> dict[str, Any]:
    parts = [float(x) for x in bbox.split(",")]
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="bbox must be swLat,swLng,neLat,neLng")
    sw_lat, sw_lng, ne_lat, ne_lng = parts

    cache_key = (
        f"map:bbox:{_quantize(sw_lat)}:{_quantize(sw_lng)}"
        f":{_quantize(ne_lat)}:{_quantize(ne_lng)}:{category}:{lang}"
    )
    cached = await get_cache(cache_key)
    if cached:
        return cached

    async with get_conn() as conn:
        rows = await ArticleQueries.get_in_bbox(
            conn, sw_lat, sw_lng, ne_lat, ne_lng,
            category=None if category == "all" else category,
        )

    articles = [
        {
            "article_id": str(r["article_id"]),
            "title": r["title"],
            "category": r["category"],
            "published_at": r["published_at"].isoformat(),
            "lat": r["lat"],
            "lng": r["lng"],
            "score": float(r["score"] or 0),
        }
        for r in rows
    ]
    result = {"articles": articles, "count": len(articles)}
    await set_cache(cache_key, result, BBOX_CACHE_TTL)
    return result


# ── GET /news/heatmap ─────────────────────────────────────────────────────────

@router.get("/heatmap")
async def get_heatmap(
    bbox: str = Query(...),
    category: str = Query("all"),
) -> dict[str, Any]:
    parts = [float(x) for x in bbox.split(",")]
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="Invalid bbox")
    sw_lat, sw_lng, ne_lat, ne_lng = parts

    cache_key = f"heatmap:{_quantize(sw_lat,1)}:{_quantize(sw_lng,1)}:{category}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    async with get_conn() as conn:
        rows = await ArticleQueries.get_heatmap(
            conn, sw_lat, sw_lng, ne_lat, ne_lng,
            category=None if category == "all" else category,
        )

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lng"], r["lat"]]},
            "properties": {
                "article_id": str(r["article_id"]),
                "category": r["category"],
                "score": float(r["score"] or 0),
            },
        }
        for r in rows
    ]
    result = {"type": "FeatureCollection", "features": features}
    await set_cache(cache_key, result, HEATMAP_CACHE_TTL)
    return result


# ── GET /news/feed ────────────────────────────────────────────────────────────

@router.get("/feed")
async def get_feed(
    category: str = Query("all"),
    page: int = Query(1, ge=1),
    lang: str = Query("en"),
    sort: str = Query("published_at"),
) -> dict[str, Any]:
    cache_key = f"feed:{category}:{lang}:{sort}:page:{page}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    async with get_conn() as conn:
        rows = await ArticleQueries.get_feed(
            conn,
            category=None if category == "all" else category,
            page=page,
            sort=sort,
        )

    articles = [
        {
            "article_id": str(r["article_id"]),
            "title": r["title"],
            "image_url": r["image_url"],
            "category": r["category"],
            "published_at": r["published_at"].isoformat(),
            "geo_place_name": r["geo_place_name"],
            "likes": r["likes"] or 0,
            "score": float(r["score"] or 0),
        }
        for r in rows
    ]
    result = {"articles": articles, "page": page}
    ttl = FEED_P1_CACHE_TTL if page == 1 else FEED_PN_CACHE_TTL
    await set_cache(cache_key, result, ttl)
    return result


# ── GET /news/:id ─────────────────────────────────────────────────────────────

@router.get("/{article_id}")
async def get_article(
    article_id: uuid.UUID,
    lang: str = Query("en"),
    _: OptionalUser = None,
) -> dict[str, Any]:
    cache_key = f"article:{article_id}:{lang}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    async with get_conn() as conn:
        row = await ArticleQueries.get_by_id(conn, article_id)
        if not row:
            raise HTTPException(status_code=404, detail="Article not found")

        summary_row = await TranslationQueries.get(conn, article_id, "summary")
        trans_row = await TranslationQueries.get(conn, article_id, lang) if lang != "en" else None
        await EngagementQueries.increment_view(conn, article_id)

    result = {
        "article_id": str(row["article_id"]),
        "source": row["source"],
        "title": row["title"],
        "body": row["body"],
        "image_url": row["image_url"],
        "author": row["author"],
        "published_at": row["published_at"].isoformat(),
        "category": row["category"],
        "geo_place_name": row["geo_place_name"],
        "language": row["language"],
        "summary": summary_row["summary"] if summary_row else None,
        "likes": row["likes"] or 0,
        "dislikes": row["dislikes"] or 0,
        "view_count": row["view_count"] or 0,
        "score": float(row["score"] or 0),
        "translation": {
            "title": trans_row["title"],
            "summary": trans_row["summary"],
        } if trans_row else None,
    }
    await set_cache(cache_key, result, ARTICLE_CACHE_TTL)
    return result


# ── POST /news/:id/like & /news/:id/dislike ────────────────────────────────────

async def _handle_reaction(
    article_id: uuid.UUID,
    user_id: uuid.UUID,
    reaction: str,
) -> dict[str, Any]:
    existing = await like_idempotency_check(str(user_id), str(article_id))
    if existing == reaction:
        return {"status": "already_reacted", "reaction": reaction}

    event_type = LikeEventType.LIKE if reaction == "like" else LikeEventType.DISLIKE
    event = LikeEvent(
        user_id=user_id,
        article_id=article_id,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
    )
    get_producer().produce(
        topic="like-events",
        value=event.model_dump(mode="json"),
        key=str(article_id),
    )
    return {"status": "ok", "reaction": reaction}


@router.post("/{article_id}/like")
async def like_article(
    article_id: uuid.UUID,
    user_id: CurrentUser,
) -> dict[str, Any]:
    return await _handle_reaction(article_id, user_id, "like")


@router.post("/{article_id}/dislike")
async def dislike_article(
    article_id: uuid.UUID,
    user_id: CurrentUser,
) -> dict[str, Any]:
    return await _handle_reaction(article_id, user_id, "dislike")
