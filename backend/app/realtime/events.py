"""Publishing of realtime events through PostgreSQL NOTIFY.

``pg_notify`` inside a transaction is delivered only after COMMIT, so listeners never see events
for rolled back changes. Every backend instance LISTENs and fans out to its WebSocket clients.
"""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CHANNEL = "nbb_events"


async def publish(session: AsyncSession, event_type: str, **data: Any) -> None:
    payload = json.dumps({"type": event_type, **data}, default=str)
    if len(payload) > 7000:  # NOTIFY payload limit is 8000 bytes
        payload = json.dumps({"type": event_type})
    await session.execute(text("SELECT pg_notify(:channel, :payload)"), {"channel": CHANNEL, "payload": payload})
