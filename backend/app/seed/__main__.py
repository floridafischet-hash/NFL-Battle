"""Seed master data and (optionally) a complete demo.

python -m app.seed            # teams + initial admin (+ demo if SEED_DEMO_DATA=true and DB is empty)
python -m app.seed --demo     # force demo data (only if no season exists yet)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import secrets
import string
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update

from app.core.config import get_settings, is_placeholder
from app.core.db import dispose_engine, get_sessionmaker
from app.core.security import Principal, hash_password
from app.models import (
    Bracket,
    ChatMessage,
    Match,
    Notification,
    Prediction,
    Season,
    SystemMessage,
    Team,
    User,
)
from app.models.enums import MatchStatus, ResultSource, Role
from app.seed.teams import NFL_TEAMS, default_logo_url
from app.services import bot
from app.services.bracket_engine import Pick, slots_in_resolution_order
from app.services.brackets import load_context, picks_by_slot
from app.services.match_admin import (
    activate_season,
    compute_lock_at,
    create_season,
    generate_wild_card,
    set_participants,
)
from app.services.results import apply_result

log = logging.getLogger("seed")

DEMO_USERS = [
    ("florian", "Florian", 0.70),
    ("dennis", "Dennis", 0.80),
    ("stefan", "Stefan", 0.60),
    ("marcel", "Marcel", 0.55),
    ("lisa", "Lisa", 0.65),
    ("kevin", "Kevin", 0.50),
    ("tobi", "Tobi", 0.75),
]

SCORE_WINNER = [17, 20, 21, 23, 24, 27, 28, 30, 31, 34, 35, 38]
SCORE_LOSER = [7, 10, 13, 14, 16, 17, 20, 21, 23, 24, 27, 28]


def random_password(length: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def banner(text: str) -> None:
    line = "=" * min(100, len(text) + 4)
    log.warning("\n%s\n  %s\n%s", line, text, line)


async def ensure_teams(session) -> dict[str, Team]:
    existing = {t.abbreviation: t for t in (await session.execute(select(Team))).scalars()}
    for abbr, city, short, conf, division, primary, secondary in NFL_TEAMS:
        if abbr not in existing:
            team = Team(
                name=f"{city} {short}",
                short_name=short,
                abbreviation=abbr,
                city=city,
                conference=conf,
                division=division,
                logo_url=default_logo_url(abbr),
                primary_color=primary,
                secondary_color=secondary,
            )
            session.add(team)
            existing[abbr] = team
    await session.flush()
    return existing


async def ensure_admin(session) -> User | None:
    settings = get_settings()
    username = settings.admin_username.strip().lower()
    admin = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if admin is not None:
        return admin
    password = settings.admin_password
    if is_placeholder(password):
        password = random_password(12)
        banner(f"Initialer Admin: Benutzername '{username}', Passwort '{password}' – bitte nach dem Login ändern")
    admin = User(
        username=username,
        display_name=settings.admin_display_name,
        role=Role.ADMIN,
        password_hash=hash_password(password),
    )
    session.add(admin)
    await session.flush()
    log.info("created initial admin account '%s'", username)
    return admin


# ---------------------------------------------------------------------------------------------- demo


def local(dt_str: str) -> datetime:
    """Parse 'YYYY-MM-DD HH:MM' in the app timezone."""
    tz = ZoneInfo(get_settings().app_timezone)
    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=tz).astimezone(UTC)


class Demo:
    def __init__(self, session, admin: User, users: list[User], teams: dict[str, Team]):
        self.session = session
        self.admin = admin
        self.principal = Principal("user", admin.display_name, frozenset({"USER", "ADMIN"}), admin)
        self.users = users
        self.teams = teams
        self.favor = {u.username: f for (u, (_, _, f)) in zip(users, DEMO_USERS, strict=True)}

    async def marks(self) -> dict[str, int]:
        s = self.session
        return {
            "chat": (await s.execute(select(func.coalesce(func.max(ChatMessage.id), 0)))).scalar_one(),
            "system": (await s.execute(select(func.coalesce(func.max(SystemMessage.id), 0)))).scalar_one(),
            "notif": (await s.execute(select(func.coalesce(func.max(Notification.id), 0)))).scalar_one(),
        }

    async def backdate(self, marks: dict[str, int], when: datetime, read: bool = True) -> None:
        s = self.session
        await s.execute(update(ChatMessage).where(ChatMessage.id > marks["chat"]).values(created_at=when))
        await s.execute(update(SystemMessage).where(SystemMessage.id > marks["system"]).values(created_at=when))
        values = {"created_at": when}
        if read:
            values["read_at"] = when + timedelta(hours=1)
        await s.execute(update(Notification).where(Notification.id > marks["notif"]).values(**values))

    async def say(self, username: str, text: str, when: datetime) -> None:
        user = next(u for u in self.users if u.username == username)
        self.session.add(ChatMessage(user_id=user.id, body=text, created_at=when))
        await self.session.flush()

    async def fill_picks(
        self,
        season: Season,
        rng_seed: int,
        only_slots: set[str] | None = None,
        overrides: dict[tuple[str, str], tuple[str, int | None, int | None]] | None = None,
        fix_probability: float = 1.0,
    ) -> None:
        """Create (or repair) every user's bracket directly (bypasses the lock – seed only)."""
        ctx = await load_context(self.session, season)
        seeds = ctx.seeds
        for user in self.users:
            rng = random.Random(f"{rng_seed}-{user.username}-{only_slots and sorted(only_slots)}")
            bracket = (
                (
                    await self.session.execute(
                        select(Bracket).where(Bracket.user_id == user.id, Bracket.season_id == season.id)
                    )
                )
                .unique()
                .scalar_one_or_none()
            )
            if bracket is None:
                bracket = Bracket(user_id=user.id, season_id=season.id)
                self.session.add(bracket)
                await self.session.flush()
                await self.session.refresh(bracket, ["predictions"])
            if only_slots is not None and rng.random() > fix_probability:
                continue
            picks = picks_by_slot(bracket.predictions, ctx.by_id)
            for slot_def in slots_in_resolution_order():
                slot = slot_def.slot
                if only_slots is not None and slot not in only_slots:
                    continue
                resolved = ctx.resolve(picks)
                r = resolved[slot]
                if not r.teams_known or r.pick_state == "valid":
                    continue
                home, away = r.home_team_id, r.away_team_id
                better, worse = (home, away) if seeds.get(home, 99) <= seeds.get(away, 99) else (away, home)
                winner = better if rng.random() < self.favor[user.username] else worse
                ws = rng.choice(SCORE_WINNER)
                ls = rng.choice([x for x in SCORE_LOSER if x < ws])
                override = (overrides or {}).get((user.username, slot))
                if override and self.teams[override[0]].id in (home, away):
                    winner, ws, ls = self.teams[override[0]].id, override[1], override[2]
                match = ctx.by_slot[slot]
                pred = next((p for p in bracket.predictions if p.match_id == match.id), None)
                if pred is None:
                    pred = Prediction(bracket_id=bracket.id, match_id=match.id, winner_team_id=winner)
                    bracket.predictions.append(pred)
                pred.winner_team_id, pred.winner_score, pred.loser_score = winner, ws, ls
                pred.updated_via = "SEED"
                picks[slot] = Pick(winner, ws, ls)
            if only_slots is None:
                bracket.submitted_at = datetime.now(UTC) - timedelta(days=30)
        await self.session.flush()

    async def schedule(self, season: Season, kickoffs: dict[str, datetime]) -> None:
        for m in (await self.session.execute(select(Match).where(Match.season_id == season.id))).unique().scalars():
            if m.slot in kickoffs:
                m.kickoff_at = kickoffs[m.slot]
                m.lock_at = compute_lock_at(season, m.kickoff_at)
        await self.session.flush()

    async def result(self, season: Season, slot: str, home_score: int, away_score: int) -> None:
        match = (
            (await self.session.execute(select(Match).where(Match.season_id == season.id, Match.slot == slot)))
            .unique()
            .scalar_one()
        )
        match.status = MatchStatus.LOCKED
        await self.session.flush()
        marks = await self.marks()
        await apply_result(self.session, match.id, home_score, away_score, self.principal, ResultSource.ADMIN)
        when = (match.kickoff_at or datetime.now(UTC)) + timedelta(hours=3, minutes=20)
        await self.session.execute(update(Match).where(Match.id == match.id).values(finalized_at=when))
        await self.backdate(marks, when)

    async def setup_season(self, name: str, year: int, field: dict[str, list[str]], announce_at: datetime) -> Season:
        season = await create_season(
            self.session,
            self.principal,
            name,
            year,
            {
                "winner_points": 1,
                "exact_score_points": 3,
                "champion_bonus": 3,
                "score_tips_enabled": True,
                "lock_minutes_before_kickoff": 0,
            },
        )
        entries = []
        for conf in ("AFC", "NFC"):
            for seed, abbr in enumerate(field[conf], start=1):
                entries.append((self.teams[abbr].id, seed))
        await set_participants(self.session, self.principal, season, entries)
        await activate_season(self.session, self.principal, season)
        marks = await self.marks()
        await generate_wild_card(self.session, self.principal, season)
        await self.backdate(marks, announce_at)
        return season

    async def play(
        self,
        season: Season,
        rounds: list[tuple[dict[str, datetime], dict[str, tuple[int, int]]]],
        overrides: dict | None = None,
        fix_probability: float = 0.85,
    ) -> None:
        """rounds: [(kickoffs, results)] in chronological order; results may be partial."""
        first = True
        for kickoffs, results in rounds:
            await self.schedule(season, kickoffs)
            if first:
                await self.fill_picks(season, season.year, overrides=overrides)
                first = False
            else:
                await self.fill_picks(
                    season, season.year, only_slots=set(kickoffs), overrides=overrides, fix_probability=fix_probability
                )
            for slot, (hs, as_) in sorted(results.items(), key=lambda kv: kickoffs.get(kv[0]) or datetime.now(UTC)):
                await self.result(season, slot, hs, as_)


async def seed_demo(session, admin: User, teams: dict[str, Team]) -> None:
    settings = get_settings()
    if (await session.execute(select(func.count(Season.id)))).scalar_one() > 0:
        log.info("seasons already exist – demo data skipped")
        return
    # every demo user gets an own random password (printed once) unless DEMO_USER_PASSWORD is set
    shared = None if is_placeholder(settings.demo_user_password) else settings.demo_user_password
    users = []
    created: list[str] = []
    for username, display, _ in DEMO_USERS:
        user = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if user is None:
            password = shared or random_password(10)
            user = User(
                username=username,
                display_name=display,
                role=Role.USER,
                password_hash=hash_password(password),
            )
            session.add(user)
            if shared is None:
                created.append(f"{username}: {password}")
        users.append(user)
    if created:
        banner("Demo-Benutzer (bitte Passwörter weitergeben, danach ändern lassen):\n  " + "\n  ".join(created))
    await session.flush()
    demo = Demo(session, admin, users, teams)
    await bot.get_bot_user(session)

    # ---------------- 2024/2025 (results modelled on the real playoffs)
    s1 = await demo.setup_season(
        "2024/2025",
        2024,
        {
            "AFC": ["KC", "BUF", "BAL", "HOU", "LAC", "PIT", "DEN"],
            "NFC": ["DET", "PHI", "TB", "LAR", "MIN", "WAS", "GB"],
        },
        local("2025-01-06 10:00"),
    )
    await demo.play(
        s1,
        [
            (
                {
                    "AFC-WC-3": local("2025-01-11 22:30"),
                    "AFC-WC-2": local("2025-01-12 02:00"),
                    "AFC-WC-1": local("2025-01-12 19:00"),
                    "NFC-WC-2": local("2025-01-12 22:30"),
                    "NFC-WC-1": local("2025-01-13 02:15"),
                    "NFC-WC-3": local("2025-01-14 02:00"),
                },
                {
                    "AFC-WC-3": (32, 12),
                    "AFC-WC-2": (28, 14),
                    "AFC-WC-1": (31, 7),
                    "NFC-WC-2": (20, 23),
                    "NFC-WC-1": (22, 10),
                    "NFC-WC-3": (27, 9),
                },
            ),
            (
                {
                    "AFC-DIV-1": local("2025-01-18 22:30"),
                    "NFC-DIV-1": local("2025-01-19 02:00"),
                    "NFC-DIV-2": local("2025-01-19 21:00"),
                    "AFC-DIV-2": local("2025-01-20 00:30"),
                },
                {"AFC-DIV-1": (23, 14), "NFC-DIV-1": (31, 45), "NFC-DIV-2": (28, 22), "AFC-DIV-2": (27, 25)},
            ),
            (
                {"NFC-CONF": local("2025-01-26 21:00"), "AFC-CONF": local("2025-01-27 00:30")},
                {"NFC-CONF": (55, 23), "AFC-CONF": (32, 29)},
            ),
            ({"SB": local("2025-02-10 00:30")}, {"SB": (22, 40)}),
        ],
        overrides={("dennis", "NFC-CONF"): ("PHI", 34, 24), ("lisa", "AFC-WC-2"): ("BAL", 28, 14)},
    )

    # ---------------- 2025/2026 (fictional)
    s2 = await demo.setup_season(
        "2025/2026",
        2025,
        {
            "AFC": ["DEN", "NE", "JAX", "PIT", "HOU", "BUF", "LAC"],
            "NFC": ["SEA", "CHI", "PHI", "CAR", "LAR", "SF", "GB"],
        },
        local("2026-01-05 10:00"),
    )
    await demo.play(
        s2,
        [
            (
                {
                    "AFC-WC-1": local("2026-01-10 22:30"),
                    "NFC-WC-1": local("2026-01-11 02:00"),
                    "AFC-WC-2": local("2026-01-11 19:00"),
                    "NFC-WC-2": local("2026-01-11 22:30"),
                    "AFC-WC-3": local("2026-01-12 02:15"),
                    "NFC-WC-3": local("2026-01-13 02:00"),
                },
                {
                    "AFC-WC-1": (24, 27),
                    "NFC-WC-1": (27, 20),
                    "AFC-WC-2": (31, 23),
                    "NFC-WC-2": (20, 24),
                    "AFC-WC-3": (17, 21),
                    "NFC-WC-3": (23, 30),
                },
            ),
            (
                {
                    "AFC-DIV-1": local("2026-01-17 22:30"),
                    "NFC-DIV-1": local("2026-01-18 02:00"),
                    "AFC-DIV-2": local("2026-01-18 21:00"),
                    "NFC-DIV-2": local("2026-01-19 00:30"),
                },
                {"AFC-DIV-1": (30, 20), "NFC-DIV-1": (34, 17), "AFC-DIV-2": (27, 24), "NFC-DIV-2": (24, 27)},
            ),
            (
                {"AFC-CONF": local("2026-01-25 21:00"), "NFC-CONF": local("2026-01-26 00:30")},
                {"AFC-CONF": (24, 20), "NFC-CONF": (31, 27)},
            ),
            ({"SB": local("2026-02-09 00:30")}, {"SB": (21, 28)}),
        ],
        overrides={("florian", "SB"): ("SEA", 28, 21), ("tobi", "AFC-CONF"): ("DEN", 24, 20)},
    )

    # ---------------- 2026/2027 (current, fictional, relative to now)
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    s3 = await demo.setup_season(
        "2026/2027",
        2026,
        {
            "AFC": ["KC", "BUF", "BAL", "HOU", "MIA", "LAC", "PIT"],
            "NFC": ["PHI", "DET", "SF", "TB", "MIN", "GB", "LAR"],
        },
        now - timedelta(days=12),
    )
    tz = ZoneInfo(settings.app_timezone)

    def at(days: int, hour: int, minute: int = 0) -> datetime:
        day = (now + timedelta(days=days)).astimezone(tz)
        return day.replace(hour=hour, minute=minute).astimezone(UTC)

    await demo.play(
        s3,
        [
            (
                {
                    "AFC-WC-1": at(-9, 22, 30),
                    "AFC-WC-2": at(-8, 2),
                    "AFC-WC-3": at(-8, 19),
                    "NFC-WC-1": at(-8, 22, 30),
                    "NFC-WC-2": at(-7, 2, 15),
                    "NFC-WC-3": at(-6, 2),
                },
                {
                    "AFC-WC-1": (27, 17),
                    "AFC-WC-2": (28, 14),
                    "AFC-WC-3": (24, 20),
                    "NFC-WC-1": (31, 23),
                    "NFC-WC-2": (20, 23),
                    "NFC-WC-3": (17, 24),
                },
            ),
            (
                {
                    "AFC-DIV-1": at(-2, 22, 30),
                    "NFC-DIV-1": at(-1, 2),
                    "AFC-DIV-2": at(1, 21),
                    "NFC-DIV-2": at(2, 0, 30),
                },
                {"AFC-DIV-1": (30, 21), "NFC-DIV-1": (20, 27)},
            ),
        ],
        overrides={
            ("dennis", "AFC-WC-2"): ("BAL", 28, 14),
            ("marcel", "NFC-WC-2"): ("GB", 23, 20),
            ("lisa", "NFC-WC-2"): ("GB", 24, 20),
            ("florian", "AFC-DIV-2"): ("BUF", 27, 24),
            ("tobi", "AFC-DIV-2"): ("BAL", 24, 17),
        },
        fix_probability=0.8,
    )

    chat = [
        ("marcel", "Packers! Wer hat das kommen sehen? 🧀🔥", at(-7, 5, 40)),
        ("lisa", "Ich 😎 Steht so in meinem Bracket.", at(-7, 5, 52)),
        ("kevin", "Mein NFC-Bracket ist nach einem Wochenende komplett zerstört 😂", at(-6, 9, 15)),
        ("dennis", "Chiefs wie immer eiskalt in den Playoffs.", at(-1, 2, 10)),
        ("stefan", "Packers schon wieder?! Das wird langsam unheimlich.", at(-1, 5, 45)),
        ("florian", "Bills gegen Ravens – ich bleib bei Buffalo! 🦬", now - timedelta(hours=3)),
        ("tobi", "Ravens by 7. Merkt euch das. 💜", now - timedelta(hours=1, minutes=20)),
        ("stefan", "Wer bringt beim Super Bowl die Chips mit? 🍕", now - timedelta(minutes=35)),
    ]
    for username, text, when in chat:
        await demo.say(username, text, when)
    await renumber_chat(session)
    # keep the latest notifications unread for the demo
    await session.execute(
        update(Notification).where(Notification.created_at >= now - timedelta(days=3)).values(read_at=None)
    )
    log.info("demo data created: 3 seasons, %d users", len(users))


async def renumber_chat(session) -> None:
    """Seeded messages were back-dated; give them ids in chronological order (chat is ordered by id)."""
    from sqlalchemy import text

    await session.execute(text("CREATE TEMP TABLE chat_tmp ON COMMIT DROP AS SELECT * FROM chat_messages"))
    await session.execute(text("DELETE FROM chat_messages"))
    await session.execute(
        text(
            "INSERT INTO chat_messages (user_id, body, upload_id, system_message_id, created_at, deleted_at, "
            "deleted_by) "
            "SELECT user_id, body, upload_id, system_message_id, created_at, deleted_at, deleted_by "
            "FROM chat_tmp ORDER BY created_at, id"
        )
    )


async def main(force_demo: bool) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    async with get_sessionmaker()() as session:
        teams = await ensure_teams(session)
        admin = await ensure_admin(session)
        await bot.get_bot_user(session)
        await session.commit()
        if settings.seed_demo_data or force_demo:
            if admin is None:
                log.warning("demo data needs an admin account (set ADMIN_PASSWORD)")
            else:
                await seed_demo(session, admin, teams)
                await session.commit()
    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="create demo data even if SEED_DEMO_DATA is false")
    asyncio.run(main(parser.parse_args().demo))
