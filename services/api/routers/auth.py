"""Auth router — register, login, refresh, logout."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from jose import JWTError

import sys
sys.path.insert(0, "/app/shared")

from auth.jwt import (
    TokenType,
    create_access_token,
    create_refresh_token,
    remaining_ttl_seconds,
    verify_token,
)
from auth.password import hash_password, verify_password
from db.connection import get_conn
from db.queries import UserQueries
from models.user import TokenResponse, UserCreate, UserLogin, UserOut
from cache.helpers import blacklist_jwt

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate) -> UserOut:
    async with get_conn() as conn:
        existing = await UserQueries.get_by_email(conn, body.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        user_id = uuid.uuid4()
        await UserQueries.create(
            conn,
            user_id=user_id,
            email=body.email,
            username=body.username,
            password_hash=hash_password(body.password),
        )
        user = await UserQueries.get_by_id(conn, user_id)

    return UserOut(
        user_id=user["user_id"],
        email=user["email"],
        username=user["username"],
        created_at=user["created_at"],
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin) -> TokenResponse:
    async with get_conn() as conn:
        user = await UserQueries.get_by_email(conn, body.email)

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token, _ = create_access_token(user["user_id"])
    refresh_token, _ = create_refresh_token(user["user_id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    authorization: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        token_data = verify_token(token, expected_type=TokenType.REFRESH)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    await blacklist_jwt(token_data.jti, remaining_ttl_seconds(token_data))

    access_token, _ = create_access_token(token_data.user_id)
    refresh_token, _ = create_refresh_token(token_data.user_id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_200_OK, response_model=None)
async def logout(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        return
    token = authorization.removeprefix("Bearer ").strip()
    try:
        token_data = verify_token(token, expected_type=TokenType.ACCESS)
        await blacklist_jwt(token_data.jti, remaining_ttl_seconds(token_data))
    except JWTError:
        pass
