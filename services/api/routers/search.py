"""Search router — full-text search via Elasticsearch."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Query
from elasticsearch import AsyncElasticsearch

router = APIRouter()
logger = logging.getLogger("api.search")

_es: AsyncElasticsearch | None = None
ES_INDEX = "geonews_articles"


def get_es() -> AsyncElasticsearch:
    global _es
    if _es is None:
        _es = AsyncElasticsearch(
            hosts=[os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")]
        )
    return _es


@router.get("")
async def search(
    q: str = Query(..., min_length=2, max_length=200),
    category: str = Query("all"),
    lang: str = Query("en"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    must_clauses: list[dict] = [
        {
            "multi_match": {
                "query": q,
                "fields": ["title^3", "body"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        }
    ]
    filter_clauses: list[dict] = [{"term": {"status": "processed"}}]

    if category and category.lower() != "all":
        filter_clauses.append({"term": {"category": category}})

    es_query = {
        "query": {
            "bool": {
                "must": must_clauses,
                "filter": filter_clauses,
            }
        },
        "sort": [{"_score": "desc"}, {"published_at": "desc"}],
        "from": (page - 1) * page_size,
        "size": page_size,
        "highlight": {
            "fields": {
                "title": {"number_of_fragments": 0},
                "body": {"number_of_fragments": 2, "fragment_size": 150},
            }
        },
    }

    try:
        resp = await get_es().search(index=ES_INDEX, body=es_query)
        hits = resp["hits"]["hits"]
        total = resp["hits"]["total"]["value"]
    except Exception as exc:
        logger.error("Elasticsearch query failed: %s", exc)
        return {"articles": [], "total": 0, "query": q}

    articles = []
    for hit in hits:
        src = hit["_source"]
        articles.append(
            {
                "article_id": src.get("article_id"),
                "title": src.get("title"),
                "category": src.get("category"),
                "published_at": src.get("published_at"),
                "geo_place_name": src.get("geo_place_name"),
                "score": hit["_score"],
                "highlights": hit.get("highlight", {}),
            }
        )

    return {
        "articles": articles,
        "total": total,
        "query": q,
        "page": page,
    }
