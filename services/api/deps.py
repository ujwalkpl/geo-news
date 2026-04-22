"""FastAPI dependency injection helpers."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError

import sys
sys.path.insert(0, "/app/shared")

from auth.jwt import TokenType, verify_token
from cache.helpers import is_jwt_blacklisted


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    """Extract and validate JWT from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    try:
        token_data = verify_token(token, expected_type=TokenType.ACCESS)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if await is_jwt_blacklisted(token_data.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    return token_data.user_id


async def get_optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> uuid.UUID | None:
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


CurrentUser = Annotated[uuid.UUID, Depends(get_current_user)]
OptionalUser = Annotated[uuid.UUID | None, Depends(get_optional_user)]
