"""WebSocket Server — real-time broadcast of new articles to connected clients.

Architecture:
- Subscribes to Kafka topic new-articles-pub
- Maintains a set of connected WebSocket clients
- Broadcasts new article coords + metadata to all connected clients
- Cloud Run session affinity keeps clients on the same instance

Connection URL: ws://host/ws?token=<jwt>   (optional auth for user-specific features)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
import uuid
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

from auth.jwt import TokenType, verify_token
from kafka.consumer import KafkaConsumerClient
from cache.helpers import delete_ws_session, set_ws_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("websocket")

app = FastAPI(title="GeoNews WebSocket Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

INSTANCE_ID = os.environ.get("K_REVISION", str(uuid.uuid4())[:8])

# ── Connection Manager ─────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self) -> None:
        # Maps ws → optional user_id for user-specific filtering
        self._connections: dict[WebSocket, str | None] = {}

    async def connect(self, ws: WebSocket, user_id: str | None) -> None:
        await ws.accept()
        self._connections[ws] = user_id
        logger.info(
            "Client connected user_id=%s total=%d",
            user_id or "anon", len(self._connections),
        )

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.pop(ws, None)
        logger.info("Client disconnected total=%d", len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast to all connected clients concurrently.

        Uses asyncio.gather so all sends fire simultaneously — a slow or
        dead client never delays messages to healthy clients.
        Each send has a 5s timeout; clients that exceed it are dropped.
        """
        if not self._connections:
            return

        payload = json.dumps(message)
        connections = list(self._connections)

        async def _send(ws: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(ws.send_text(payload), timeout=5.0)
                return None      # success
            except Exception:
                return ws        # mark as dead

        results = await asyncio.gather(*(_send(ws) for ws in connections))

        # Drop connections that timed out or errored
        for ws in results:
            if ws is not None:
                self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    user_id: str | None = None
    if token:
        try:
            token_data = verify_token(token, expected_type=TokenType.ACCESS)
            user_id = str(token_data.user_id)
        except Exception:
            pass  # allow anonymous connections

    await manager.connect(ws, user_id)

    if user_id:
        await set_ws_session(user_id, INSTANCE_ID)

    try:
        while True:
            # Keep connection alive — client pings are handled automatically
            # We don't expect data from clients in this implementation
            await asyncio.sleep(30)
            try:
                await ws.send_text(json.dumps({"type": "ping"}))
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)
        if user_id:
            await delete_ws_session(user_id)


# ── Kafka consumer background task ───────────────────────────────────────────

async def kafka_consumer_loop() -> None:
    """Background task: polls Kafka new-articles-pub and broadcasts to clients."""
    consumer = KafkaConsumerClient(
        topics=["new-articles-pub"],
        group_id=f"websocket-{INSTANCE_ID}",
    )
    logger.info("Kafka consumer loop started for new-articles-pub")

    loop = asyncio.get_event_loop()

    def _poll() -> dict | None:
        return consumer.poll_one(timeout=0.5)

    try:
        while True:
            # Run blocking Kafka poll in thread pool
            msg = await loop.run_in_executor(None, _poll)
            if msg is None:
                await asyncio.sleep(0)
                continue

            article = msg["value"]
            broadcast_payload = {
                "type": "new_article",
                "article_id": article.get("article_id"),
                "lat": article.get("lat"),
                "lng": article.get("lng"),
                "category": article.get("category"),
                "title": article.get("title"),
                "score": article.get("score", 0),
                "image_url": article.get("image_url"),
            }

            if manager.connection_count > 0:
                await manager.broadcast(broadcast_payload)
                logger.debug(
                    "Broadcast article_id=%s to %d clients",
                    article.get("article_id"),
                    manager.connection_count,
                )

            # Commit after broadcast
            consumer.commit(msg)

    except asyncio.CancelledError:
        pass
    finally:
        consumer.close()
        logger.info("Kafka consumer loop stopped")


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(kafka_consumer_loop())
    logger.info("WebSocket server started instance=%s", INSTANCE_ID)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "instance": INSTANCE_ID,
        "connections": manager.connection_count,
    }
