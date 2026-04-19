"""User Upload Service — FastAPI endpoints for user-submitted news with GPS.

Flow:
  1. POST /upload/signed-url  — validate metadata, return a GCS signed URL
  2. UI uploads image DIRECTLY to GCS using the signed URL (backend never sees bytes)
  3. POST /upload/confirm     — receive metadata + image_url, publish to Kafka

This means image bytes never pass through this service — no RAM spike,
no backend bandwidth cost, and unlimited concurrent uploads.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, "/app/shared")

from auth.jwt import TokenType, verify_token
from kafka.producer import KafkaProducerClient
from models.article import ArticleSource, RawArticle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("upload")

app = FastAPI(title="GeoNews Upload Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

GCS_BUCKET = os.environ["GCS_BUCKET_NAME"]
RAW_NEWS_TOPIC = "raw-news"
GPS_ACCURACY_LIMIT_METRES = 100.0
IP_GEO_TOLERANCE_KM = 200.0
MAX_IMAGE_BYTES = 8 * 1024 * 1024   # 8MB
SIGNED_URL_TTL_MINUTES = 15
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

_producer: KafkaProducerClient | None = None


def get_producer() -> KafkaProducerClient:
    global _producer
    if _producer is None:
        _producer = KafkaProducerClient()
    return _producer


# ── Auth dependency ────────────────────────────────────────────────────────────

async def require_auth(authorization: Annotated[str | None, Header()] = None) -> uuid.UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        token_data = verify_token(token, expected_type=TokenType.ACCESS)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return token_data.user_id


# ── IP geolocation check ───────────────────────────────────────────────────────

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def check_ip_geoloc(request: Request, lat: float, lng: float) -> bool:
    """Cross-reference GPS coords against IP geolocation.

    Returns True if plausible, False if likely spoofed.
    Non-blocking — failure defaults to True (allow upload).
    """
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "")
    ip = client_ip.split(",")[0].strip()
    if not ip or ip in ("127.0.0.1", "::1"):
        return True
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "lat,lon,status"},
                timeout=3.0,
            )
            data = resp.json()
            if data.get("status") != "success":
                return True
            dist_km = _haversine_km(lat, lng, float(data["lat"]), float(data["lon"]))
            if dist_km > IP_GEO_TOLERANCE_KM:
                logger.warning(
                    "GPS/IP mismatch: GPS=(%.4f,%.4f) IP=(%.4f,%.4f) dist=%.0fkm",
                    lat, lng, float(data["lat"]), float(data["lon"]), dist_km,
                )
                return False
    except Exception as exc:
        logger.debug("IP geoloc check failed (non-blocking): %s", exc)
    return True


# ── Signed URL generation ──────────────────────────────────────────────────────

def generate_signed_url(object_name: str, content_type: str) -> str:
    """Generate a GCS signed URL for a direct PUT upload from the browser.

    The URL is valid for SIGNED_URL_TTL_MINUTES and scoped to the exact
    object_name and content_type — the browser cannot upload anything else.
    Uses google-cloud-storage (sync but called once per request, not in a loop).
    """
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(object_name)

    url = blob.generate_signed_url(
        expiration=timedelta(minutes=SIGNED_URL_TTL_MINUTES),
        method="PUT",
        content_type=content_type,
        version="v4",
    )
    return url


# ── Request / Response models ──────────────────────────────────────────────────

class SignedUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    size_bytes: int = Field(gt=0)
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
    accuracy: float = Field(gt=0)


class SignedUrlResponse(BaseModel):
    signed_url: str
    object_name: str
    image_url: str
    article_id: str
    expires_in_minutes: int


class ConfirmUploadRequest(BaseModel):
    article_id: str
    title: str = Field(min_length=3, max_length=300, default="")
    text: str = Field(min_length=10, max_length=5000)
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
    accuracy: float = Field(gt=0)
    image_url: str | None = None   # GCS public URL — set only if image was uploaded


# ── Step 1: Request a signed URL ───────────────────────────────────────────────

@app.post("/upload/signed-url", response_model=SignedUrlResponse)
async def get_signed_url(
    request: Request,
    body: SignedUrlRequest,
    user_id: Annotated[uuid.UUID, Depends(require_auth)],
) -> SignedUrlResponse:
    """Validate metadata and return a GCS signed URL for direct browser upload.

    The UI uses this URL to PUT the image straight to GCS.
    Image bytes never pass through this service.
    """
    # Validate content type
    if body.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported image type. Allowed: {', '.join(ALLOWED_CONTENT_TYPES)}",
        )

    # Validate file size before upload (declared size — not cryptographically enforced,
    # but GCS signed URL can be scoped with max_bytes in production)
    if body.size_bytes > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)}MB limit.",
        )

    # Validate GPS accuracy
    if body.accuracy > GPS_ACCURACY_LIMIT_METRES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"GPS accuracy {body.accuracy:.0f}m exceeds limit of {GPS_ACCURACY_LIMIT_METRES:.0f}m.",
        )

    # Cross-reference GPS with IP geolocation (non-blocking, logs warning only)
    plausible = await check_ip_geoloc(request, body.lat, body.lng)
    if not plausible:
        logger.warning("Possible GPS spoofing from user_id=%s", user_id)

    # Generate deterministic object name — article_id is created here so it can
    # be returned to the UI and reused in /upload/confirm
    article_id = uuid.uuid4()
    ext = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else "jpg"
    object_name = f"uploads/{article_id}/{uuid.uuid4()}.{ext}"
    cdn_host = os.environ.get("CDN_HOST", f"https://storage.googleapis.com/{GCS_BUCKET}")
    image_url = f"{cdn_host}/{object_name}"

    signed_url = generate_signed_url(object_name, body.content_type)

    logger.info("Signed URL issued: article_id=%s user_id=%s object=%s", article_id, user_id, object_name)

    return SignedUrlResponse(
        signed_url=signed_url,
        object_name=object_name,
        image_url=image_url,
        article_id=str(article_id),
        expires_in_minutes=SIGNED_URL_TTL_MINUTES,
    )


# ── Step 2: UI uploads directly to GCS using the signed URL (no backend involved)


# ── Step 3: Confirm upload and publish to Kafka ────────────────────────────────

@app.post("/upload/confirm", status_code=status.HTTP_202_ACCEPTED)
async def confirm_upload(
    body: ConfirmUploadRequest,
    user_id: Annotated[uuid.UUID, Depends(require_auth)],
) -> dict:
    """Receive article metadata after the UI has uploaded the image to GCS.

    Publishes to raw-news Kafka topic so the full pipeline processes it:
    - Summarizer: passthrough (user wrote the text)
    - Classifier: skip geocoding (GPS provided), run keyword category only
    - Translator: run normally (user may write in any language)
    - Aggregator: joins 3 results, writes to Postgres
    """
    article_id = uuid.UUID(body.article_id)

    article = RawArticle(
        article_id=article_id,
        source=ArticleSource.USER_UPLOAD,
        title=body.title or body.text[:120],
        body=body.text,
        image_url=body.image_url,
        published_at=datetime.now(timezone.utc),
        lat=body.lat,
        lng=body.lng,
        user_id=str(user_id),
        is_user_upload=True,   # signals pipeline to skip summarization + geocoding
    )

    get_producer().produce(
        topic=RAW_NEWS_TOPIC,
        value=article.model_dump(mode="json"),
        key=str(article_id),
    )
    logger.info("User upload confirmed and published: article_id=%s user_id=%s", article_id, user_id)

    return {
        "article_id": str(article_id),
        "status": "accepted",
        "message": "Your post is being processed and will appear on the map shortly.",
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
