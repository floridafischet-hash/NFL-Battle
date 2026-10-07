"""Test setup: a real PostgreSQL database (TEST_DATABASE_URL), schema via Alembic, tables truncated
between tests. The app runs in-process through httpx's ASGI transport."""

import os
import tempfile

os.environ.setdefault("TEST_DATABASE_URL", "postgresql+psycopg://postgres@/nfl_test?host=/tmp&port=5433")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["APP_ENV"] = "test"
os.environ["DB_DISABLE_POOL"] = "true"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["PASSWORD_HASH_ITERATIONS"] = "1000"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-0123456789"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="nbb-uploads-")
os.environ["AGENT_RESULT_MIN_MINUTES_AFTER_KICKOFF"] = "0"
os.environ["RESULT_AGENT_CONFIRM_RUNS"] = "1"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("OPENAI_API_KEY_FILE", None)

from datetime import UTC, datetime, timedelta  # noqa: E402
from typing import Any  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import get_sessionmaker  # noqa: E402
from app.core.ratelimit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.models.enums import Role  # noqa: E402
from app.seed.__main__ import ensure_teams  # noqa: E402
from app.services.bot import get_bot_user  # noqa: E402

BASE = os.path.dirname(os.path.dirname(__file__))
PASSWORD = "secret123"

FIELD = {
    "AFC": ["KC", "BUF", "BAL", "HOU", "MIA", "LAC", "PIT"],
    "NFC": ["PHI", "DET", "SF", "TB", "MIN", "GB", "LAR"],
}


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    sync_url = get_settings().database_url
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    cfg = Config(os.path.join(BASE, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BASE, "alembic"))
    command.upgrade(cfg, "head")
    yield


TABLES = (
    "audit_logs, app_settings, result_reports, agent_runs, notifications, chat_messages, system_messages, uploads, "
    "hall_of_fame, leaderboards, scores, prediction_changes, predictions, brackets, matches, season_teams, seasons, "
    "teams, users"
)


@pytest.fixture(autouse=True)
async def clean_db():
    async with get_sessionmaker()() as session:
        await session.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        await ensure_teams(session)
        await get_bot_user(session)
        await session.commit()
    limiter.reset()
    yield


async def create_user(username: str, role: Role = Role.USER, password: str = PASSWORD, active: bool = True) -> User:
    async with get_sessionmaker()() as session:
        user = User(
            username=username,
            display_name=username.capitalize(),
            role=role,
            password_hash=hash_password(password),
            is_active=active,
        )
        session.add(user)
        await session.commit()
        return user


class Api:
    """Small wrapper around httpx with an optional bearer token."""

    def __init__(self, token: str | None = None):
        self.token = token
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    def _headers(self, extra: dict | None = None) -> dict:
        headers = dict(extra or {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get(self, url: str, **kw) -> httpx.Response:
        return await self.client.get(url, headers=self._headers(kw.pop("headers", None)), **kw)

    async def post(self, url: str, json: Any = None, **kw) -> httpx.Response:
        return await self.client.post(url, json=json, headers=self._headers(kw.pop("headers", None)), **kw)

    async def put(self, url: str, json: Any = None, **kw) -> httpx.Response:
        return await self.client.put(url, json=json, headers=self._headers(kw.pop("headers", None)), **kw)

    async def patch(self, url: str, json: Any = None, **kw) -> httpx.Response:
        return await self.client.patch(url, json=json, headers=self._headers(kw.pop("headers", None)), **kw)

    async def delete(self, url: str, **kw) -> httpx.Response:
        return await self.client.delete(url, headers=self._headers(kw.pop("headers", None)), **kw)


async def login(username: str, password: str = PASSWORD) -> Api:
    api = Api()
    r = await api.post("/api/auth/login", {"username": username, "password": password})
    assert r.status_code == 200, r.text
    api.token = r.json()["access_token"]
    return api


@pytest.fixture
async def admin() -> Api:
    await create_user("admin", Role.ADMIN)
    return await login("admin")


@pytest.fixture
async def players() -> dict[str, Api]:
    out = {}
    for name in ("florian", "dennis", "stefan"):
        await create_user(name)
        out[name] = await login(name)
    return out


async def team_ids(api: Api) -> dict[str, int]:
    r = await api.get("/api/teams")
    return {t["abbreviation"]: t["id"] for t in r.json()}


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


async def setup_season(admin: Api, year: int = 2030, kickoff_in: timedelta = timedelta(days=1), **config) -> dict:
    """Create an active season with seeds and Wild Card pairings; returns {season, matches(by slot), teams}."""
    r = await admin.post("/api/admin/seasons", {"name": f"{year}/{year + 1}", "year": year, **config})
    assert r.status_code == 201, r.text
    season = r.json()
    teams = await team_ids(admin)
    entries = [{"team_id": teams[abbr], "seed": i + 1} for conf in ("AFC", "NFC") for i, abbr in enumerate(FIELD[conf])]
    r = await admin.put(f"/api/admin/seasons/{season['id']}/teams", entries)
    assert r.status_code == 200, r.text
    r = await admin.post(f"/api/admin/seasons/{season['id']}/activate")
    assert r.status_code == 200, r.text
    r = await admin.post(f"/api/admin/seasons/{season['id']}/generate-wildcard")
    assert r.status_code == 200, r.text
    matches = await admin_matches(admin, season["id"])
    kickoff = datetime.now(UTC) + kickoff_in
    for slot, m in matches.items():
        if slot.endswith(("WC-1", "WC-2", "WC-3")):
            r = await admin.patch(f"/api/admin/matches/{m['id']}", {"kickoff_at": iso(kickoff)})
            assert r.status_code == 200, r.text
    return {"season": season, "matches": await admin_matches(admin, season["id"]), "teams": teams}


async def admin_matches(admin: Api, season_id: int) -> dict[str, dict]:
    r = await admin.get(f"/api/admin/seasons/{season_id}/matches")
    assert r.status_code == 200, r.text
    return {m["slot"]: m for m in r.json()}


async def pick(api: Api, season_id: int, slot: str, team_id: int, ws: int | None = None, ls: int | None = None):
    return await api.put(
        f"/api/seasons/{season_id}/bracket/me/picks/{slot}",
        {"winner_team_id": team_id, "winner_score": ws, "loser_score": ls},
    )


async def lock(admin: Api, match_id: int) -> None:
    r = await admin.post(f"/api/admin/matches/{match_id}/status", {"action": "lock"})
    assert r.status_code == 200, r.text


async def result(admin: Api, match_id: int, home: int, away: int) -> dict:
    r = await admin.post(f"/api/admin/matches/{match_id}/result", {"home_score": home, "away_score": away})
    assert r.status_code == 200, r.text
    return r.json()
