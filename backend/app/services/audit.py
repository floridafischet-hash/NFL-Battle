from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.models import AuditLog
from app.models.enums import ActorType


def actor_fields(principal: Principal | None) -> dict[str, Any]:
    if principal is None:
        return {"actor_type": ActorType.SYSTEM.value, "actor_user_id": None, "actor_label": "System"}
    if principal.kind == "agent":
        return {"actor_type": ActorType.AGENT.value, "actor_user_id": None, "actor_label": principal.label[:120]}
    return {
        "actor_type": (ActorType.ADMIN if principal.is_admin else ActorType.USER).value,
        "actor_user_id": principal.user_id,
        "actor_label": principal.label[:120],
    }


def audit(
    session: AsyncSession,
    principal: Principal | None,
    action: str,
    object_type: str,
    object_id: Any = None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    source: str = "WEB",
) -> AuditLog:
    """Add an audit record to the current transaction (committed together with the change)."""
    entry = AuditLog(
        **actor_fields(principal),
        action=action,
        object_type=object_type,
        object_id=None if object_id is None else str(object_id),
        old_value=old,
        new_value=new,
        source=source,
        ip_address=principal.ip if principal else None,
    )
    session.add(entry)
    return entry
