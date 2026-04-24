"""Translator Service — translates articles using MarianMT + Google Translate fallback.

Consumer group: translator-group
Input topic:    raw-news
Output topic:   processed-news (field: translations)

Strategy:
  - Detect source language with langdetect
  - High-volume pairs (en→es, en→fr, en→de): MarianMT (HuggingFace, self-hosted)
  - Low-resource pairs: Google Translate API fallback
  - Always produce: es, fr, de translations
  - Runs for both NewsAPI articles and user uploads (user may write in any language)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langdetect import LangDetectException, detect
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

load_dotenv(Path(__file__).parent.parent.parent / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

from base_service import BaseKafkaService
from models.article import ProcessedField

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

TARGET_LANGUAGES = ["es", "fr", "de"]

_MARIAN_PAIRS: dict[tuple[str, str], str] = {
    ("en", "es"): "Helsinki-NLP/opus-mt-en-es",
    ("en", "fr"): "Helsinki-NLP/opus-mt-en-fr",
    ("en", "de"): "Helsinki-NLP/opus-mt-en-de",
}


class TranslatorService(BaseKafkaService):
    """Reads raw-news, translates title + body, publishes to processed-news."""

    group_id = "translator-group"
    input_topics = ["raw-news"]
    output_topic = "processed-news"

    def __init__(self) -> None:
        super().__init__()
        # Lazy-loaded MarianMT pipelines keyed by (src, tgt)
        self._pipelines: dict[tuple[str, str], Any] = {}

    # ── Core logic ────────────────────────────────────────────────────────────

    def process(self, msg: dict[str, Any]) -> dict[str, Any]:
        article_id = msg["article_id"]
        title = msg.get("title", "")
        body = msg.get("body") or ""
        declared_lang = msg.get("language")

        src_lang = declared_lang or self._detect_language(f"{title} {body}")

        translations = []
        for tgt in TARGET_LANGUAGES:
            translated_title = self._translate(title, src_lang, tgt)
            translated_summary = self._translate(body[:300], src_lang, tgt)
            if translated_title or translated_summary:
                translations.append({
                    "language_code": tgt,
                    "title": translated_title,
                    "summary": translated_summary,
                })

        self._logger.info(
            "Translated article_id=%s lang=%s → %d translations",
            article_id, src_lang, len(translations),
        )

        return {
            "article_id": article_id,
            "field": ProcessedField.TRANSLATIONS.value,
            "data": {
                "translations": translations,
                "detected_language": src_lang,
            },
        }

    def on_error(self, msg: dict[str, Any], exc: Exception) -> dict[str, Any] | None:
        # Publish empty translations so the join counter still reaches 3
        self._logger.warning(
            "Translation failed for article_id=%s (%s) — publishing empty translations",
            msg.get("article_id"), exc,
        )
        return {
            "article_id": msg["article_id"],
            "field": ProcessedField.TRANSLATIONS.value,
            "data": {"translations": [], "detected_language": "en"},
        }

    # ── Private: translation ──────────────────────────────────────────────────

    def _translate(self, text: str, src_lang: str, tgt_lang: str) -> str | None:
        if src_lang == tgt_lang:
            return None
        result = self._translate_marian(text, src_lang, tgt_lang)
        if result:
            return result
        try:
            return self._translate_google(text, tgt_lang)
        except Exception as exc:
            self._logger.warning("Google Translate failed %s→%s: %s", src_lang, tgt_lang, exc)
            return None

    def _translate_marian(self, text: str, src: str, tgt: str) -> str | None:
        key = (src, tgt)
        if key not in _MARIAN_PAIRS:
            return None
        if key not in self._pipelines:
            from transformers import pipeline  # lazy import — avoids slow startup
            self._logger.info("Loading MarianMT model: %s", _MARIAN_PAIRS[key])
            self._pipelines[key] = pipeline(
                "translation",
                model=_MARIAN_PAIRS[key],
                max_length=512,
                device=-1,  # CPU
            )
        result = self._pipelines[key](text[:500])
        return result[0]["translation_text"]

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _translate_google(self, text: str, target: str) -> str:
        import httpx
        api_key = os.environ.get("GOOGLE_TRANSLATE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_TRANSLATE_API_KEY not configured — skipping fallback")
        resp = httpx.post(
            "https://translation.googleapis.com/language/translate/v2",
            params={"key": api_key},
            json={"q": text[:500], "target": target, "format": "text"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["data"]["translations"][0]["translatedText"]

    @staticmethod
    def _detect_language(text: str) -> str:
        try:
            return detect(text[:500])
        except LangDetectException:
            return "en"


if __name__ == "__main__":
    TranslatorService().start()
