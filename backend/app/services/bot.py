"""NFL Bot: posts structured system messages into the chat."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ChatMessage, Match, SystemMessage, Team, User
from app.models.enums import Role, SystemMessageType
from app.realtime.events import publish

BOT_USERNAME = "nfl-bot"
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


async def get_bot_user(session: AsyncSession) -> User:
    bot = (await session.execute(select(User).where(User.username == BOT_USERNAME))).scalar_one_or_none()
    if bot is None:
        bot = User(username=BOT_USERNAME, display_name="NFL Bot", is_bot=True, role=Role.USER, avatar_url=None)
        session.add(bot)
        await session.flush()
    return bot


def local_time(dt: datetime | None) -> str:
    if dt is None:
        return "Termin offen"
    local = dt.astimezone(ZoneInfo(get_settings().app_timezone))
    return f"{WEEKDAYS[local.weekday()]} {local:%d.%m. %H:%M} Uhr"


def team_payload(team: Team | None) -> dict[str, Any] | None:
    if team is None:
        return None
    return {
        "id": team.id,
        "name": team.name,
        "short_name": team.short_name,
        "abbreviation": team.abbreviation,
        "logo_url": team.logo_url,
        "primary_color": team.primary_color,
        "secondary_color": team.secondary_color,
    }


def match_payload(match: Match) -> dict[str, Any]:
    from app.services.bracket_engine import ROUND_LABELS

    return {
        "id": match.id,
        "slot": match.slot,
        "round": match.round.value,
        "round_label": ROUND_LABELS[match.round],
        "home": team_payload(match.home_team),
        "away": team_payload(match.away_team),
        "home_score": match.home_score,
        "away_score": match.away_score,
        "winner_team_id": match.winner_team_id,
        "kickoff_at": match.kickoff_at.isoformat() if match.kickoff_at else None,
    }


async def post(
    session: AsyncSession,
    type_: SystemMessageType,
    text: str,
    payload: dict[str, Any] | None = None,
    *,
    season_id: int | None = None,
    match_id: int | None = None,
    dedupe_key: str | None = None,
) -> ChatMessage | None:
    """Create a system message + chat entry. Returns None if the dedupe key was already used."""
    if dedupe_key is not None:
        exists = (
            await session.execute(select(SystemMessage.id).where(SystemMessage.dedupe_key == dedupe_key))
        ).scalar_one_or_none()
        if exists is not None:
            return None
    bot = await get_bot_user(session)
    system = SystemMessage(
        type=type_, season_id=season_id, match_id=match_id, payload=payload or {}, dedupe_key=dedupe_key
    )
    session.add(system)
    await session.flush()
    message = ChatMessage(user_id=bot.id, body=text[:4000], system_message_id=system.id)
    session.add(message)
    await session.flush()
    await publish(session, "chat_message", id=message.id)
    return message


def final_text(match: Match, points: list[dict[str, Any]], leaderboard: list[dict[str, Any]], correction: bool) -> str:
    home = match.home_team.short_name if match.home_team else "?"
    away = match.away_team.short_name if match.away_team else "?"
    lines = ["KORREKTUR" if correction else "FINAL", f"{home} {match.home_score} : {match.away_score} {away}"]
    if points:
        lines.append("")
        lines.append("Auswertung:")
        for p in points:
            lines.append(f"{p['display_name']} {p['icon']} +{p['points']}")
    if leaderboard:
        lines.append("")
        lines.append("Neue Rangliste:")
        for row in leaderboard:
            lines.append(f"{row['rank']} {row['display_name']} {row['points']}")
    return "\n".join(lines)


def pick_icon(has_pick: bool, winner_correct: bool, exact_correct: bool) -> str:
    if exact_correct:
        return "🎯"
    if winner_correct:
        return "✅"
    if not has_pick:
        return "➖"
    return "❌"
