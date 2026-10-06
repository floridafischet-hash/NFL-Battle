"""WebSocket hub + PostgreSQL LISTEN bridge."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field

import psycopg
from fastapi import WebSocket
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models import ChatMessage
from app.realtime.events import CHANNEL

log = logging.getLogger(__name__)


@dataclass(eq=False)
class Connection:
    websocket: WebSocket
    user_id: uuid.UUID
    is_admin: bool
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=200))


class Hub:
    def __init__(self) -> None:
        self.connections: set[Connection] = set()
        self.listening = False  # True while the LISTEN connection is established

    def register(self, conn: Connection) -> None:
        self.connections.add(conn)

    def unregister(self, conn: Connection) -> None:
        self.connections.discard(conn)

    def online_user_ids(self) -> list[str]:
        return sorted({str(c.user_id) for c in self.connections})

    def _enqueue(self, conn: Connection, message: dict) -> None:
        try:
            conn.queue.put_nowait(message)
        except asyncio.QueueFull:
            log.warning("dropping slow websocket client %s", conn.user_id)
            self.unregister(conn)

    def broadcast(self, message: dict) -> None:
        for conn in list(self.connections):
            self._enqueue(conn, message)

    async def dispatch(self, event: dict) -> None:
        """Route a database event to the connected clients."""
        target_user = event.get("target_user_id")
        if target_user:
            for conn in list(self.connections):
                if str(conn.user_id) == target_user:
                    self._enqueue(conn, event)
            return
        if event.get("target_admins"):
            for conn in list(self.connections):
                if conn.is_admin:
                    self._enqueue(conn, event)
            return
        if event.get("type") == "chat_message" and "id" in event:
            from app.services.chat import serialize

            async with get_sessionmaker()() as session:
                message = (
                    (await session.execute(select(ChatMessage).where(ChatMessage.id == int(event["id"]))))
                    .unique()
                    .scalar_one_or_none()
                )
                if message is None:
                    return
                event = {"type": "chat_message", "message": serialize(message)}
        self.broadcast(event)


hub = Hub()


def _psycopg_dsn(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


async def listen_forever(stop: asyncio.Event) -> None:
    """Keep a LISTEN connection open and feed events into the hub (reconnects on failure)."""
    delay = 1.0
    while not stop.is_set():
        try:
            conn = await psycopg.AsyncConnection.connect(_psycopg_dsn(get_settings().database_url), autocommit=True)
            async with conn:
                await conn.execute(f"LISTEN {CHANNEL}")
                hub.listening = True
                delay = 1.0
                log.info("realtime listener connected")
                while not stop.is_set():
                    # returns after 1s without notifications so the stop flag is checked regularly
                    async for notify in conn.notifies(timeout=1.0):
                        try:
                            await hub.dispatch(json.loads(notify.payload))
                        except Exception:
                            log.exception("failed to dispatch realtime event")
        except (psycopg.Error, OSError) as exc:
            if stop.is_set():
                return
            log.warning("realtime listener error (%s), reconnecting in %.0fs", exc, delay)
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except TimeoutError:
                pass
            delay = min(delay * 2, 30)
        finally:
            hub.listening = False
