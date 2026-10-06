"""Background jobs: automatic tip lock at the deadline and reminders for open tips.

Runs in every backend instance; a PostgreSQL advisory lock makes sure only one instance works on
a tick (safe for multiple replicas / Kubernetes).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models import Bracket, Match, Prediction, User
from app.models.enums import MatchStatus, SystemMessageType
from app.realtime.events import publish
from app.services import bot
from app.services.audit import audit
from app.services.notifications import notify
from app.services.seasons import now_utc

log = logging.getLogger(__name__)
ADVISORY_LOCK_ID = 73_102_027


async def lock_due_matches(session) -> int:
    now = now_utc()
    due = list(
        (
            await session.execute(
                select(Match)
                .where(Match.status == MatchStatus.OPEN, Match.lock_at.is_not(None), Match.lock_at <= now)
                .with_for_update(of=Match, skip_locked=True)
            )
        )
        .unique()
        .scalars()
    )
    for match in due:
        match.status = MatchStatus.LOCKED
        audit(
            session,
            None,
            "MATCH_LOCKED",
            "match",
            match.id,
            {"status": "OPEN"},
            {"status": "LOCKED", "reason": "deadline"},
            source="SYSTEM",
        )
        if match.teams_known:
            text_ = (
                f"KICKOFF 🔒\n{match.home_team.short_name} vs {match.away_team.short_name}\n"
                f"Die Tipps sind jetzt gesperrt. Viel Glück!"
            )
            await bot.post(
                session,
                SystemMessageType.KICKOFF,
                text_,
                {"match": bot.match_payload(match)},
                season_id=match.season_id,
                match_id=match.id,
                dedupe_key=f"KICKOFF:{match.id}:{match.lock_at.isoformat()}",
            )
        await publish(session, "match_updated", season_id=match.season_id, match_id=match.id)
    return len(due)


async def send_open_pick_reminders(session) -> int:
    """Once per match: remind users without a valid tip when the deadline is near."""
    settings = get_settings()
    now = now_utc()
    horizon = now + timedelta(hours=settings.reminder_hours_before_lock)
    matches = list(
        (
            await session.execute(
                select(Match).where(
                    Match.status == MatchStatus.OPEN,
                    Match.home_team_id.is_not(None),
                    Match.away_team_id.is_not(None),
                    Match.lock_at.is_not(None),
                    Match.lock_at > now,
                    Match.lock_at <= horizon,
                )
            )
        )
        .unique()
        .scalars()
    )
    sent = 0
    for match in matches:
        users = list(
            (await session.execute(select(User).where(User.is_active.is_(True), User.is_bot.is_(False)))).scalars()
        )
        picked = {
            uid
            for uid, team in (
                await session.execute(
                    select(Bracket.user_id, Prediction.winner_team_id)
                    .join(Prediction, Prediction.bracket_id == Bracket.id)
                    .where(Prediction.match_id == match.id)
                )
            ).all()
            if team in (match.home_team_id, match.away_team_id)
        }
        missing = [u for u in users if u.id not in picked]
        if not missing:
            continue
        names = ", ".join(u.display_name for u in missing)
        posted = await bot.post(
            session,
            SystemMessageType.OPEN_PICKS,
            f"OFFENE TIPPS ⏰\n{match.home_team.short_name} vs {match.away_team.short_name} – Tippschluss "
            f"{bot.local_time(match.lock_at)}\nNoch nicht getippt: {names}",
            {
                "match": bot.match_payload(match),
                "users": [u.display_name for u in missing],
                "lock_at": match.lock_at.isoformat(),
            },
            season_id=match.season_id,
            match_id=match.id,
            dedupe_key=f"OPEN_PICKS:{match.id}:{match.lock_at.isoformat()}",
        )
        if posted is not None:
            await notify(
                session,
                [u.id for u in missing],
                "OPEN_PICKS",
                f"Tipp fehlt: {match.home_team.short_name} vs {match.away_team.short_name}",
                f"Tippschluss {bot.local_time(match.lock_at)}",
                "/bracket",
            )
            sent += 1
    return sent


async def run_tick() -> None:
    async with get_sessionmaker()() as session:
        got = (await session.execute(text("SELECT pg_try_advisory_xact_lock(:id)"), {"id": ADVISORY_LOCK_ID})).scalar()
        if not got:
            await session.rollback()
            return
        locked = await lock_due_matches(session)
        reminders = await send_open_pick_reminders(session)
        await session.commit()
        if locked or reminders:
            log.info("scheduler: locked=%s reminders=%s", locked, reminders)


async def scheduler_loop(stop: asyncio.Event) -> None:
    interval = get_settings().scheduler_interval_seconds
    while not stop.is_set():
        try:
            await run_tick()
        except Exception:  # keep the loop alive; errors are logged
            log.exception("scheduler tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass
