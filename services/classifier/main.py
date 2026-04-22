"""Classifier Service — NER-based geo extraction + category classification.

Consumer group: classifier-group
Input topic:    raw-news
Output topic:   processed-news (field: geo_category)

Steps for NewsAPI articles:
  1. Run spaCy NER to extract GPE/LOC entities
  2. Call Mapbox Geocoding API to resolve best entity → lat/lng
  3. Assign category using keyword heuristic

User uploads skip steps 1-2 (GPS coordinates provided by device).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx
import spacy
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

load_dotenv(Path(__file__).parent.parent.parent / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

from base_service import BaseKafkaService
from models.article import ArticleCategory, ProcessedField

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

MAPBOX_TOKEN = os.environ["MAPBOX_TOKEN"]
GEOCODE_URL = "https://api.mapbox.com/search/geocode/v6/forward"

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    ArticleCategory.AI.value: [
        "artificial intelligence", "machine learning", "deep learning",
        "neural network", "llm", "gpt", "openai", "anthropic", "gemini",
        "chatbot", "generative ai",
    ],
    ArticleCategory.TECHNOLOGY.value: [
        "software", "hardware", "smartphone", "cloud", "cybersecurity",
        "startup", "tech", "silicon valley", "semiconductor", "app",
    ],
    ArticleCategory.SPORTS.value: [
        "football", "soccer", "basketball", "tennis", "cricket",
        "olympic", "championship", "league", "tournament", "athlete",
    ],
    ArticleCategory.POLITICS.value: [
        "election", "president", "minister", "parliament", "congress",
        "senate", "government", "policy", "vote", "diplomacy", "war", "treaty",
    ],
    ArticleCategory.FINANCE.value: [
        "stock", "market", "economy", "inflation", "gdp", "bank",
        "investment", "cryptocurrency", "bitcoin", "earnings", "revenue",
    ],
    ArticleCategory.HEALTH.value: [
        "health", "medical", "disease", "vaccine", "hospital", "cancer",
        "clinical trial", "fda", "who", "pandemic", "nutrition",
    ],
    ArticleCategory.ENTERTAINMENT.value: [
        "movie", "film", "music", "celebrity", "award", "streaming",
        "netflix", "spotify", "concert", "tv show", "actor",
    ],
}


class ClassifierService(BaseKafkaService):
    """Reads raw-news, resolves geo + category, publishes to processed-news."""

    group_id = "classifier-group"
    input_topics = ["raw-news"]
    output_topic = "processed-news"

    def __init__(self) -> None:
        super().__init__()
        self._nlp = self._load_spacy()

    # ── Core logic ────────────────────────────────────────────────────────────

    def process(self, msg: dict[str, Any]) -> dict[str, Any]:
        article_id = msg["article_id"]
        title = msg.get("title", "")
        body = msg.get("body") or ""
        combined = f"{title}. {body}"

        category = self._classify_category(combined)

        if msg.get("is_user_upload"):
            # GPS provided directly by device — skip NER + geocoding
            lat = float(msg["lat"])
            lng = float(msg["lng"])
            geo_place_name = msg.get("geo_place_name")
            self._logger.info(
                "Skipping NER/geocoding for user_upload article_id=%s", article_id
            )
        else:
            entities = self._extract_geo_entities(combined)
            lat, lng, geo_place_name = self._resolve_location(entities)

        return {
            "article_id": article_id,
            "field": ProcessedField.GEO_CATEGORY.value,
            "data": {
                "category": category,
                "lat": lat,
                "lng": lng,
                "geo_place_name": geo_place_name,
                # Pass raw article fields so aggregator can INSERT into Postgres
                "source": msg.get("source"),
                "original_url": msg.get("original_url"),
                "title": msg.get("title", ""),
                "body": msg.get("body", ""),
                "image_url": msg.get("image_url"),
                "author": msg.get("author"),
                "published_at": msg.get("published_at"),
                "language": msg.get("language", "en"),
            },
        }

    # ── Private: category classification ──────────────────────────────────────

    def _classify_category(self, text: str) -> str:
        lower = text.lower()
        scores: dict[str, int] = {
            cat: sum(1 for kw in keywords if kw in lower)
            for cat, keywords in _CATEGORY_KEYWORDS.items()
        }
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else ArticleCategory.GENERAL.value

    # ── Private: NER + geocoding ───────────────────────────────────────────────

    def _extract_geo_entities(self, text: str) -> list[str]:
        doc = self._nlp(text[:5000])
        seen: set[str] = set()
        entities: list[str] = []
        for ent in doc.ents:
            if ent.label_ in ("GPE", "LOC") and ent.text not in seen:
                seen.add(ent.text)
                entities.append(ent.text)
            if len(entities) >= 5:
                break
        return entities

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _geocode(self, place_name: str) -> tuple[float, float] | None:
        resp = httpx.get(
            GEOCODE_URL,
            params={
                "q": place_name,
                "access_token": MAPBOX_TOKEN,
                "limit": 1,
                "types": "country,region,place,district",
            },
            timeout=5.0,
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if not features:
            return None
        coords = features[0]["geometry"]["coordinates"]  # [lng, lat]
        return float(coords[1]), float(coords[0])

    def _resolve_location(
        self, entities: list[str]
    ) -> tuple[float | None, float | None, str | None]:
        for entity in entities:
            result = self._geocode(entity)
            if result:
                return result[0], result[1], entity
        return None, None, None

    # ── Private: setup ────────────────────────────────────────────────────────

    @staticmethod
    def _load_spacy():
        try:
            nlp = spacy.load("en_core_web_sm")
            logging.getLogger("ClassifierService").info("spaCy model loaded")
            return nlp
        except OSError:
            import subprocess
            logging.getLogger("ClassifierService").warning(
                "spaCy model not found — downloading en_core_web_sm"
            )
            subprocess.run(
                [sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True
            )
            return spacy.load("en_core_web_sm")


if __name__ == "__main__":
    ClassifierService().start()
