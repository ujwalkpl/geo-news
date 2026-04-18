"""Summarizer Service — generates summaries via Gemini Flash.

Consumer group: summarizer-group
Input topic:    raw-news
Output topic:   processed-news (field: summary)

User uploads skip Gemini and passthrough the original body as the summary,
so the aggregator join counter still reaches 3.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv(Path(__file__).parent.parent.parent / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

from base_service import BaseKafkaService
from models.article import ProcessedField

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

GEMINI_MODEL = "models/gemini-2.5-flash"
SUMMARY_PROMPT = (
    "Summarise the following news article in 2-3 concise sentences. "
    "Focus on the key facts and who / what / where / when. "
    "Do not include opinions or speculation. Output only the summary text.\n\n"
    "TITLE: {title}\n\nBODY:\n{body}"
)


class SummarizerService(BaseKafkaService):
    """Reads raw-news, generates a Gemini summary, publishes to processed-news."""

    group_id = "summarizer-group"
    input_topics = ["raw-news"]
    output_topic = "processed-news"

    def __init__(self) -> None:
        super().__init__()
        self._gemini = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    # ── Core logic ────────────────────────────────────────────────────────────

    def process(self, msg: dict[str, Any]) -> dict[str, Any]:
        article_id = msg["article_id"]
        title = msg.get("title", "")
        body = msg.get("body") or msg.get("description") or ""

        if msg.get("is_user_upload"):
            # User wrote their own text — skip Gemini, passthrough as-is
            summary = body
            self._logger.info("Passthrough summary for user_upload article_id=%s", article_id)
        else:
            summary = self._call_gemini(title, body)

        return {
            "article_id": article_id,
            "field": ProcessedField.SUMMARY.value,
            "data": {"summary": summary},
        }

    def on_error(self, msg: dict[str, Any], exc: Exception) -> dict[str, Any] | None:
        # Publish an empty summary rather than DLQ so the join counter reaches 3
        self._logger.warning(
            "Gemini failed for article_id=%s (%s) — publishing empty summary",
            msg.get("article_id"), exc,
        )
        return {
            "article_id": msg["article_id"],
            "field": ProcessedField.SUMMARY.value,
            "data": {"summary": ""},
        }

    # ── Private ───────────────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_gemini(self, title: str, body: str) -> str:
        prompt = SUMMARY_PROMPT.format(title=title, body=body[:4000])
        response = self._gemini.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"max_output_tokens": 200, "temperature": 0.3},
        )
        return response.text.strip()


if __name__ == "__main__":
    SummarizerService().start()
