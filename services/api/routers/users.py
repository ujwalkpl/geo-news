"""Users router — profile and reaction history."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

import sys
sys.path.insert(0, "/app/shared")

from db.connection import get_conn
from db.queries import UserQueries
from models.user import UserOut

from deps import CurrentUser

router = APIRouter()


@router.get("/me", response_model=UserOut)
async def get_me(user_id: CurrentUser) -> UserOut:
    async with get_conn() as conn:
        user = await UserQueries.get_by_id(conn, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(
        user_id=user["user_id"],
        email=user["email"],
        username=user["username"],
        created_at=user["created_at"],
    )


@router.get("/me/reactions")
async def get_my_reactions(
    user_id: CurrentUser,
    page: int = Query(1, ge=1),
) -> dict[str, Any]:
    page_size = 20
    offset = (page - 1) * page_size
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT ur.article_id, ur.reaction, ur.created_at,
                   a.title, a.category, a.image_url
            FROM user_reactions ur
            JOIN articles a USING (article_id)
            WHERE ur.user_id = $1
            ORDER BY ur.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id, page_size, offset,
        )
    return {
        "reactions": [
            {
                "article_id": str(r["article_id"]),
                "reaction": r["reaction"],
                "created_at": r["created_at"].isoformat(),
                "title": r["title"],
                "category": r["category"],
                "image_url": r["image_url"],
            }
            for r in rows
        ],
        "page": page,
    }
