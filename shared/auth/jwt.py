"""JWT creation and validation using python-jose."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel

JWT_SECRET_KEY = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "30"))


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenData(BaseModel):
    user_id: uuid.UUID
    jti: str
    token_type: TokenType
    exp: datetime


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(user_id: uuid.UUID) -> tuple[str, str]:
    """Return (encoded_token, jti)."""
    jti = str(uuid.uuid4())
    expire = _utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "type": TokenType.ACCESS.value,
        "exp": expire,
        "iat": _utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM), jti


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str]:
    """Return (encoded_token, jti)."""
    jti = str(uuid.uuid4())
    expire = _utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "type": TokenType.REFRESH.value,
        "exp": expire,
        "iat": _utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM), jti


def decode_token(token: str) -> dict[str, Any]:
    """Decode without verifying expiry (for refresh flows). Raises JWTError."""
    return jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        options={"verify_exp": False},
    )


def verify_token(token: str, expected_type: TokenType = TokenType.ACCESS) -> TokenData:
    """Decode and validate. Raises JWTError on any failure."""
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    token_type = payload.get("type")
    if token_type != expected_type.value:
        raise JWTError(f"Expected token type '{expected_type.value}', got '{token_type}'")
    return TokenData(
        user_id=uuid.UUID(payload["sub"]),
        jti=payload["jti"],
        token_type=TokenType(token_type),
        exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
    )


def remaining_ttl_seconds(token_data: TokenData) -> int:
    """Return seconds until token expires (0 if already expired)."""
    delta = token_data.exp - _utcnow()
    return max(0, int(delta.total_seconds()))
