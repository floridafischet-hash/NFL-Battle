"""Admin endpoints (role ADMIN only)."""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.security import CurrentAdmin, DBSession, hash_password
from app.core.text import clean_display_name
from app.models import (
    AgentRun,
    AuditLog,
    Bracket,
    Prediction,
    PredictionChange,
    ResultReport,
    Season,
    Team,
    User,
)
from app.models.enums import ChangeRequestStatus, Conference, ReportStatus, ResultSource, Role, UploadKind
from app.realtime.events import publish
from app.schemas.common import MatchOut, SeasonOut, TeamOut
from app.schemas.serializers import change_request_out
from app.services import agent as agent_service
from app.services import app_settings, change_requests, match_admin, result_agent
from app.services.audit import audit
from app.services.brackets import load_context
from app.services.results import apply_result, reset_result
from app.services.scoring import recalculate_season
from app.services.seasons import get_season, match_out, not_found, now_utc, team_out
from app.services.uploads import store_image

router = APIRouter(prefix="/api/admin", tags=["admin"])

USERNAME_RE = re.compile(r"^[a-z0-9._-]{2,32}$")
HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


# ------------------------------------------------------------------ users


class UserCreateIn(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=6, max_length=200)
    role: Literal["USER", "ADMIN"] = "USER"

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.match(v):
            raise ValueError("2–32 Zeichen: a–z, 0–9, Punkt, Minus, Unterstrich")
        return v

    @field_validator("display_name")
    @classmethod
    def _display(cls, v: str) -> str:
        return clean_display_name(v)


class UserUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    role: Literal["USER", "ADMIN"] | None = None
    is_active: bool | None = None

    @field_validator("display_name")
    @classmethod
    def _display(cls, v: str | None) -> str | None:
        return None if v is None else clean_display_name(v)


class PasswordResetIn(BaseModel):
    password: str = Field(min_length=6, max_length=200)


def user_admin_out(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "avatar_url": u.avatar_url,
        "role": u.role.value,
        "is_active": u.is_active,
        "created_at": u.created_at,
        "last_login_at": u.last_login_at,
        "last_seen_at": u.last_seen_at,
    }


async def _user(session, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None or user.is_bot:
        raise not_found("Benutzer")
    return user


@router.get("/users")
async def list_users(admin: CurrentAdmin, session: DBSession) -> list[dict[str, Any]]:
    users = (await session.execute(select(User).where(User.is_bot.is_(False)).order_by(User.display_name))).scalars()
    return [user_admin_out(u) for u in users]


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreateIn, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    user = User(
        username=body.username,
        display_name=body.display_name.strip(),
        password_hash=await asyncio.to_thread(hash_password, body.password),
        role=Role(body.role),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Benutzername ist bereits vergeben.")
    audit(
        session,
        admin,
        "USER_CREATED",
        "user",
        user.id,
        None,
        {"username": user.username, "display_name": user.display_name, "role": user.role.value},
        source="ADMIN",
    )
    await session.commit()
    return user_admin_out(user)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID, body: UserUpdateIn, admin: CurrentAdmin, session: DBSession
) -> dict[str, Any]:
    user = await _user(session, user_id)
    old = {"display_name": user.display_name, "role": user.role.value, "is_active": user.is_active}
    if user.id == admin.user_id and (body.role == "USER" or body.is_active is False):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Du kannst dir selbst nicht die Adminrechte entziehen oder dich sperren."
        )
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
    if body.role is not None:
        user.role = Role(body.role)
    if body.is_active is not None:
        user.is_active = body.is_active
    new = {"display_name": user.display_name, "role": user.role.value, "is_active": user.is_active}
    if old != new:
        action = "USER_UPDATED"
        if old["is_active"] != new["is_active"]:
            action = "USER_ACTIVATED" if user.is_active else "USER_BLOCKED"
        elif old["role"] != new["role"]:
            action = "USER_ROLE_CHANGED"
        audit(session, admin, action, "user", user.id, old, new, source="ADMIN")
    await session.commit()
    return user_admin_out(user)


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(user_id: uuid.UUID, body: PasswordResetIn, admin: CurrentAdmin, session: DBSession) -> None:
    user = await _user(session, user_id)
    user.password_hash = await asyncio.to_thread(hash_password, body.password)
    user.token_version += 1
    audit(session, admin, "USER_PASSWORD_RESET", "user", user.id, None, None, source="ADMIN")
    await session.commit()


@router.get("/users/{user_id}/predictions")
async def user_predictions(
    user_id: uuid.UUID, admin: CurrentAdmin, session: DBSession, season_id: int
) -> dict[str, Any]:
    user = await _user(session, user_id)
    season = await get_season(session, season_id)
    rows = (
        (
            await session.execute(
                select(Prediction)
                .join(Bracket, Bracket.id == Prediction.bracket_id)
                .where(Bracket.user_id == user.id, Bracket.season_id == season.id)
            )
        )
        .unique()
        .scalars()
    )
    return {
        "user": user_admin_out(user),
        "predictions": [
            {
                "match": match_out(p.match),
                "winner_team": team_out(p.winner_team),
                "winner_score": p.winner_score,
                "loser_score": p.loser_score,
                "updated_at": p.updated_at,
                "updated_via": p.updated_via,
            }
            for p in sorted(rows, key=lambda p: p.match_id)
        ],
    }


# ------------------------------------------------------------------ seasons


class SeasonConfig(BaseModel):
    winner_points: int = Field(default=1, ge=0, le=100)
    exact_score_points: int = Field(default=3, ge=0, le=100)
    champion_bonus: int = Field(default=3, ge=0, le=100)
    score_tips_enabled: bool = True
    lock_minutes_before_kickoff: int = Field(default=0, ge=0, le=10080)


class SeasonCreateIn(SeasonConfig):
    name: str = Field(pattern=r"^\d{4}/\d{4}$")
    year: int = Field(ge=2000, le=2100)


class SeasonUpdateIn(BaseModel):
    winner_points: int | None = Field(default=None, ge=0, le=100)
    exact_score_points: int | None = Field(default=None, ge=0, le=100)
    champion_bonus: int | None = Field(default=None, ge=0, le=100)
    score_tips_enabled: bool | None = None
    lock_minutes_before_kickoff: int | None = Field(default=None, ge=0, le=10080)


class ParticipantIn(BaseModel):
    team_id: int
    seed: int = Field(ge=1, le=7)


@router.post("/seasons", status_code=status.HTTP_201_CREATED, response_model=SeasonOut)
async def create_season(body: SeasonCreateIn, admin: CurrentAdmin, session: DBSession) -> Season:
    config = body.model_dump(exclude={"name", "year"})
    season = await match_admin.create_season(session, admin, body.name, body.year, config)
    await session.commit()
    return await get_season(session, season.id)


@router.patch("/seasons/{season_id}", response_model=SeasonOut)
async def update_season(season_id: int, body: SeasonUpdateIn, admin: CurrentAdmin, session: DBSession) -> Season:
    season = await get_season(session, season_id)
    changes = body.model_dump(exclude_none=True)
    old = {k: getattr(season, k) for k in changes}
    for k, v in changes.items():
        setattr(season, k, v)
    if old != changes:
        audit(
            session,
            admin,
            "SCORING_CONFIG_CHANGED" if any("points" in k or "bonus" in k for k in changes) else "SEASON_UPDATED",
            "season",
            season.id,
            old,
            changes,
            source="ADMIN",
        )
        await publish(session, "season_updated", season_id=season.id)
    await session.commit()
    return season


@router.post("/seasons/{season_id}/activate", response_model=SeasonOut)
async def activate_season(season_id: int, admin: CurrentAdmin, session: DBSession) -> Season:
    season = await get_season(session, season_id)
    await match_admin.activate_season(session, admin, season)
    await session.commit()
    return season


@router.put("/seasons/{season_id}/teams", response_model=list[TeamOut])
async def set_participants(season_id: int, body: list[ParticipantIn], admin: CurrentAdmin, session: DBSession):
    season = await get_season(session, season_id)
    if len(body) > 14:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Maximal 14 Playoff-Teams (7 pro Conference).")
    rows = await match_admin.set_participants(session, admin, season, [(p.team_id, p.seed) for p in body])
    await session.commit()
    seeds = {r.team_id: r.seed for r in rows}
    return [team_out(r.team, seeds) for r in rows]


@router.post("/seasons/{season_id}/generate-wildcard")
async def generate_wildcard(season_id: int, admin: CurrentAdmin, session: DBSession) -> list[MatchOut]:
    season = await get_season(session, season_id)
    matches = await match_admin.generate_wild_card(session, admin, season)
    await session.commit()
    return [match_out(m) for m in matches]


@router.post("/seasons/{season_id}/announce")
async def announce(season_id: int, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    season = await get_season(session, season_id)
    count = await match_admin.announce_open_matchups(session, season)
    await session.commit()
    return {"announced": count}


@router.post("/seasons/{season_id}/recalculate")
async def recalculate(season_id: int, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    season = await get_season(session, season_id)
    result = await recalculate_season(session, season, admin)
    await session.commit()
    return result


@router.get("/seasons/{season_id}/matches")
async def admin_matches(season_id: int, admin: CurrentAdmin, session: DBSession) -> list[dict[str, Any]]:
    season = await get_season(session, season_id)
    ctx = await load_context(session, season)
    pending = dict(
        (
            await session.execute(
                select(ResultReport.match_id, func.count(ResultReport.id))
                .where(ResultReport.status == ReportStatus.REVIEW_REQUIRED)
                .group_by(ResultReport.match_id)
            )
        ).all()
    )
    picks = dict(
        (
            await session.execute(
                select(Prediction.match_id, func.count(Prediction.id))
                .join(Bracket, Bracket.id == Prediction.bracket_id)
                .where(Bracket.season_id == season.id)
                .group_by(Prediction.match_id)
            )
        ).all()
    )
    out = []
    for m in ctx.matches:
        item = match_out(m, ctx.seeds, ctx.now).model_dump()
        item["review_required"] = pending.get(m.id, 0)
        item["picks"] = picks.get(m.id, 0)
        item["result_check_requested_at"] = m.result_check_requested_at
        out.append(item)
    return out


# ------------------------------------------------------------------ teams


class TeamIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    short_name: str = Field(min_length=2, max_length=40)
    abbreviation: str = Field(min_length=2, max_length=4, pattern=r"^[A-Za-z]{2,4}$")
    city: str | None = Field(default=None, max_length=60)
    conference: Conference
    division: str | None = Field(default=None, max_length=10)
    logo_url: str | None = Field(default=None, max_length=500)
    primary_color: str = Field(default="#334155", pattern=HEX_COLOR)
    secondary_color: str = Field(default="#94a3b8", pattern=HEX_COLOR)
    is_active: bool = True

    @field_validator("logo_url")
    @classmethod
    def _logo(cls, v: str | None) -> str | None:
        if v and not (v.startswith("/") or v.startswith("https://")):
            raise ValueError("Logo-URL muss mit / oder https:// beginnen")
        return v or None


@router.post("/teams", status_code=status.HTTP_201_CREATED, response_model=TeamOut)
async def create_team(body: TeamIn, admin: CurrentAdmin, session: DBSession) -> Team:
    team = Team(**{**body.model_dump(), "abbreviation": body.abbreviation.upper()})
    session.add(team)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Kürzel bereits vergeben.")
    audit(session, admin, "TEAM_CREATED", "team", team.id, None, body.model_dump(mode="json"), source="ADMIN")
    await session.commit()
    return team


@router.put("/teams/{team_id}", response_model=TeamOut)
async def update_team(team_id: int, body: TeamIn, admin: CurrentAdmin, session: DBSession) -> Team:
    team = await session.get(Team, team_id)
    if team is None:
        raise not_found("Team")
    old = TeamOut.model_validate(team).model_dump(mode="json")
    for k, v in body.model_dump().items():
        setattr(team, k, v.upper() if k == "abbreviation" else v)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Kürzel bereits vergeben.")
    audit(session, admin, "TEAM_UPDATED", "team", team.id, old, body.model_dump(mode="json"), source="ADMIN")
    await publish(session, "teams_updated")
    await session.commit()
    return team


@router.post("/teams/{team_id}/logo", response_model=TeamOut)
async def upload_logo(team_id: int, admin: CurrentAdmin, session: DBSession, file: UploadFile = File(...)) -> Team:
    team = await session.get(Team, team_id)
    if team is None:
        raise not_found("Team")
    upload = await store_image(session, file, UploadKind.LOGO, admin.user_id)
    old = team.logo_url
    team.logo_url = upload.url
    audit(
        session,
        admin,
        "TEAM_LOGO_UPDATED",
        "team",
        team.id,
        {"logo_url": old},
        {"logo_url": team.logo_url},
        source="ADMIN",
    )
    await publish(session, "teams_updated")
    await session.commit()
    return team


# ------------------------------------------------------------------ matches


class MatchUpdateIn(BaseModel):
    home_team_id: int | None = None
    away_team_id: int | None = None
    kickoff_at: datetime | None = None
    lock_at: datetime | None = None
    venue: str | None = Field(default=None, max_length=120)


class StatusIn(BaseModel):
    action: Literal["open", "lock", "reopen", "void"]
    lock_at: datetime | None = None


class ResultIn(BaseModel):
    home_score: int = Field(ge=0, le=99)
    away_score: int = Field(ge=0, le=99)


@router.patch("/matches/{match_id}")
async def update_match(match_id: int, body: MatchUpdateIn, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    changes = body.model_dump(exclude_unset=True)
    match = await match_admin.update_match(session, admin, match_id, changes)
    await session.commit()
    return match_out(match).model_dump()


@router.post("/matches/{match_id}/status")
async def match_status(match_id: int, body: StatusIn, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    match = await match_admin.change_status(session, admin, match_id, body.action, body.lock_at)
    await session.commit()
    return match_out(match).model_dump()


@router.post("/matches/{match_id}/result")
async def set_result(match_id: int, body: ResultIn, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    outcome = await apply_result(session, match_id, body.home_score, body.away_score, admin, ResultSource.ADMIN)
    await session.commit()
    return {
        "match": match_out(outcome.match),
        "correction": outcome.correction,
        "advanced": [match_out(m) for m in outcome.advanced],
        "season_completed": outcome.season_completed,
        "points": outcome.points,
    }


@router.post("/matches/{match_id}/reset-result")
async def reset(match_id: int, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    match = await reset_result(session, match_id, admin)
    await session.commit()
    return match_out(match).model_dump()


# ------------------------------------------------------------------ change requests


class DecisionIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.get("/change-requests")
async def list_change_requests(
    admin: CurrentAdmin, session: DBSession, status_filter: ChangeRequestStatus | None = Query(None, alias="status")
) -> list[dict[str, Any]]:
    stmt = select(PredictionChange).order_by(PredictionChange.created_at.desc()).limit(200)
    if status_filter is not None:
        stmt = stmt.where(PredictionChange.status == status_filter)
    return [change_request_out(cr) for cr in (await session.execute(stmt)).unique().scalars()]


@router.post("/change-requests/{request_id}/approve")
async def approve(request_id: int, body: DecisionIn, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    cr = await change_requests.approve(session, admin, request_id, body.note)
    cr = (await session.execute(select(PredictionChange).where(PredictionChange.id == cr.id))).unique().scalar_one()
    return change_request_out(cr)


@router.post("/change-requests/{request_id}/reject")
async def reject(request_id: int, body: DecisionIn, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    cr = await change_requests.reject(session, admin, request_id, body.note)
    cr = (await session.execute(select(PredictionChange).where(PredictionChange.id == cr.id))).unique().scalar_one()
    return change_request_out(cr)


# ------------------------------------------------------------------ result agent (ChatGPT)


class CheckIn(BaseModel):
    match_ids: list[int] | None = Field(default=None, max_length=13)


def report_out(r: ResultReport) -> dict[str, Any]:
    return {
        "id": r.id,
        "match": match_out(r.match),
        "agent_label": r.agent_label,
        "home_score": r.home_score,
        "away_score": r.away_score,
        "winner_team": team_out(r.winner_team),
        "source": r.source,
        "source_url": r.source_url,
        "reported_at": r.reported_at,
        "extra_sources": r.extra_sources,
        "status": r.status.value,
        "review_reason": r.review_reason,
        "created_at": r.created_at,
        "reviewed_at": r.reviewed_at,
    }


async def agent_config(session: DBSession) -> dict[str, Any]:
    """Configuration and usage of the result agent – never includes the API key itself."""
    settings = get_settings()
    return {
        "enabled": settings.result_agent_enabled,
        "configured": result_agent.is_configured(),
        "provider": settings.result_agent_provider,
        "has_key": bool(settings.openai_key()),
        "chatgpt_login": result_agent.codex_logged_in(),
        "model": result_agent.model_label(),
        "trusted_domains": settings.trusted_domains,
        "min_confirmations": settings.agent_min_confirmations,
        "first_check_minutes": settings.result_agent_first_check_minutes,
        "retry_minutes": settings.result_agent_retry_minutes,
        "max_calls_per_day": settings.result_agent_max_calls_per_day,
        "calls_last_24h": await result_agent.calls_last_24h(session, now_utc()),
    }


@router.get("/agent/overview")
async def agent_overview(admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    runs = (await session.execute(select(AgentRun).order_by(AgentRun.started_at.desc()).limit(50))).scalars()
    reports = (
        (await session.execute(select(ResultReport).order_by(ResultReport.created_at.desc()).limit(50)))
        .unique()
        .scalars()
    )
    runs_list = [
        {
            "id": r.id,
            "agent_label": r.agent_label,
            "kind": r.kind,
            "status": r.status.value,
            "match_id": r.match_id,
            "message": r.message,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "request_payload": r.request_payload,
        }
        for r in runs
    ]
    errors = [r for r in runs_list if r["status"] in ("ERROR", "REJECTED")]
    return {
        "config": await agent_config(session),
        "last_run": runs_list[0] if runs_list else None,
        "runs": runs_list,
        "errors": errors[:20],
        "reports": [report_out(r) for r in reports],
        "review_required": sum(1 for r in runs_list if r["status"] == "REVIEW_REQUIRED"),
    }


@router.post("/agent/check")
async def start_result_check(body: CheckIn, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    return await agent_service.request_result_check(session, admin, body.match_ids)


@router.post("/agent/test")
async def test_agent_connection(admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    result = await result_agent.test_connection()
    audit(session, admin, "AGENT_CONNECTION_TESTED", "agent", None, None, result, source="ADMIN")
    await session.commit()
    return result


@router.post("/agent/reports/{report_id}/accept")
async def accept_report(report_id: int, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    report = await agent_service.accept_report(session, admin, report_id)
    report = await session.get(ResultReport, report.id)
    return report_out(report)  # type: ignore[arg-type]


@router.post("/agent/reports/{report_id}/reject")
async def reject_report(report_id: int, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    report = await agent_service.reject_report(session, admin, report_id)
    return report_out(report)


# ------------------------------------------------------------------ greeting


class GreetingIn(BaseModel):
    king_name: str | None = Field(default=None, max_length=80)
    king_title: str | None = Field(default=None, max_length=40)

    @field_validator("king_name", "king_title")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return clean_display_name(v) if v else None


@router.get("/greeting")
async def get_greeting(admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    return await app_settings.greeting(session)


@router.put("/greeting")
async def put_greeting(body: GreetingIn, admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    old = await app_settings.greeting(session)
    await app_settings.set_value(session, app_settings.KING_NAME, body.king_name)
    await app_settings.set_value(session, app_settings.KING_TITLE, body.king_title)
    await session.flush()
    new = await app_settings.greeting(session)
    audit(session, admin, "GREETING_UPDATED", "app_settings", "greeting", old, new, source="ADMIN")
    await session.commit()
    return new


# ------------------------------------------------------------------ audit


@router.get("/audit")
async def audit_log(
    admin: CurrentAdmin,
    session: DBSession,
    action: str | None = None,
    actor_type: str | None = None,
    object_type: str | None = None,
    q: str | None = Query(None, max_length=80),
    before: int | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_type:
        stmt = stmt.where(AuditLog.actor_type == actor_type)
    if object_type:
        stmt = stmt.where(AuditLog.object_type == object_type)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            AuditLog.actor_label.ilike(like) | AuditLog.action.ilike(like) | AuditLog.object_id.ilike(like)
        )
    if before:
        stmt = stmt.where(AuditLog.id < before)
    rows = list((await session.execute(stmt)).scalars())
    actions = [
        a for (a,) in (await session.execute(select(AuditLog.action).distinct().order_by(AuditLog.action))).all()
    ]
    return {
        "items": [
            {
                "id": a.id,
                "created_at": a.created_at,
                "actor_type": a.actor_type,
                "actor_label": a.actor_label,
                "action": a.action,
                "object_type": a.object_type,
                "object_id": a.object_id,
                "old_value": a.old_value,
                "new_value": a.new_value,
                "source": a.source,
                "ip_address": a.ip_address,
            }
            for a in rows
        ],
        "next_before": rows[-1].id if len(rows) == limit else None,
        "actions": actions,
    }


@router.get("/summary")
async def summary(admin: CurrentAdmin, session: DBSession) -> dict[str, Any]:
    pending = (
        await session.execute(
            select(func.count(PredictionChange.id)).where(PredictionChange.status == ChangeRequestStatus.PENDING)
        )
    ).scalar_one()
    review = (
        await session.execute(
            select(func.count(ResultReport.id)).where(ResultReport.status == ReportStatus.REVIEW_REQUIRED)
        )
    ).scalar_one()
    users = (await session.execute(select(func.count(User.id)).where(User.is_bot.is_(False)))).scalar_one()
    last_run = (
        await session.execute(select(AgentRun).order_by(AgentRun.started_at.desc()).limit(1))
    ).scalar_one_or_none()
    return {
        "pending_change_requests": pending,
        "review_required": review,
        "users": users,
        "last_agent_run": None
        if last_run is None
        else {
            "status": last_run.status.value,
            "started_at": last_run.started_at,
            "message": last_run.message,
            "kind": last_run.kind,
        },
    }
