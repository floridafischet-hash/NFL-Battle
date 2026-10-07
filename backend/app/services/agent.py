"""Result intake pipeline: validation, provenance and admin review for results found by the
ChatGPT result agent (app.services.result_agent). Nothing here is reachable from outside – the
pipeline is only called in-process."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import Principal
from app.models import AgentRun, Match, ResultReport, Team
from app.models.enums import AgentRunStatus, MatchStatus, ReportStatus, ResultSource
from app.services.audit import audit
from app.services.notifications import notify_admins
from app.services.results import apply_result
from app.services.seasons import is_locked, match_label, now_utc


class AgentSourceIn(BaseModel):
    source: str = Field(min_length=1, max_length=120)
    source_url: str | None = Field(default=None, max_length=500)
    home_score: int = Field(ge=0, le=99)
    away_score: int = Field(ge=0, le=99)


class AgentResultIn(BaseModel):
    match_id: int
    home_score: int = Field(ge=0, le=99)
    away_score: int = Field(ge=0, le=99)
    winner: str | int | None = None
    home_team: str | int | None = None
    away_team: str | int | None = None
    source: str = Field(min_length=1, max_length=120)
    source_url: str | None = Field(default=None, max_length=500)
    timestamp: datetime | None = None
    sources: list[AgentSourceIn] = Field(default_factory=list, max_length=10)

    @field_validator("source_url")
    @classmethod
    def _http_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        parsed = urlparse(v)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url muss eine http(s)-URL sein")
        return v


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_trusted(url: str | None) -> bool:
    host = domain_of(url)
    if not host:
        return False
    return any(host == d or host.endswith("." + d) for d in get_settings().trusted_domains)


def team_matches(ref: str | int | None, team: Team | None) -> bool:
    if ref is None or team is None:
        return False
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        return int(ref) == team.id
    value = ref.strip().lower()
    candidates = {team.abbreviation.lower(), team.short_name.lower(), team.name.lower()}
    if team.city:
        candidates.add(f"{team.city} {team.short_name}".lower())
    return value in candidates


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class AgentReject(Exception):
    def __init__(self, message: str, code: int = status.HTTP_422_UNPROCESSABLE_CONTENT):
        super().__init__(message)
        self.message = message
        self.code = code


def _new_run(principal: Principal, kind: str, payload: Any) -> AgentRun:
    return AgentRun(
        agent_label=principal.label[:120],
        kind=kind,
        status=AgentRunStatus.ERROR,
        request_payload=payload if isinstance(payload, dict) else {"raw": str(payload)[:2000]},
        ip_address=principal.ip,
    )


async def _record_failure(
    session: AsyncSession,
    principal: Principal,
    kind: str,
    payload: Any,
    run_status: AgentRunStatus,
    message: str,
    match_id: int | None = None,
) -> AgentRun:
    await session.rollback()
    run = _new_run(principal, kind, payload)
    run.status = run_status
    run.message = message[:2000]
    run.match_id = match_id
    run.finished_at = now_utc()
    session.add(run)
    audit(
        session,
        principal,
        f"AGENT_{kind}_{run_status.value}",
        "agent_run",
        None,
        None,
        {"message": message[:500], "match_id": match_id},
        source="AGENT",
    )
    await session.commit()
    return run


async def process_result(
    session: AsyncSession, principal: Principal, payload: Any, force_review: str | None = None
) -> tuple[int, dict[str, Any]]:
    """Validate and process a result found by the result agent.

    ``force_review`` sends a plausible result to the admin instead of applying it (e.g. when no
    source was backed by the web search). Returns (status code, body); every call is recorded in
    agent_runs.
    """
    try:
        data = AgentResultIn.model_validate(payload)
    except ValidationError as exc:
        errors = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        run = await _record_failure(
            session, principal, "RESULT", payload, AgentRunStatus.REJECTED, f"Ungültige Nutzlast: {errors}"
        )
        return 422, {"status": "REJECTED", "run_id": run.id, "message": run.message}

    try:
        return await _process_valid_result(session, principal, data, payload, force_review)
    except AgentReject as exc:
        run = await _record_failure(
            session,
            principal,
            "RESULT",
            payload,
            AgentRunStatus.REJECTED,
            exc.message,
            data.match_id if exc.code != 404 else None,
        )
        return exc.code, {"status": "REJECTED", "run_id": run.id, "message": exc.message}
    except HTTPException as exc:
        # pipeline refused (e.g. downstream already locked) -> keep report for manual review
        message = f"Automatische Wertung nicht möglich: {exc.detail}"
        await session.rollback()
        run = _new_run(principal, "RESULT", payload)
        run.status = AgentRunStatus.REVIEW_REQUIRED
        run.message = message
        run.match_id = data.match_id
        run.finished_at = now_utc()
        session.add(run)
        await session.flush()
        report = await _create_report(
            session, run, principal, data, data.home_score, data.away_score, ReportStatus.REVIEW_REQUIRED, message
        )
        await notify_admins(
            session, "REVIEW_REQUIRED", "ChatGPT-Ergebnis muss geprüft werden", message, "/admin?tab=agent"
        )
        audit(
            session,
            principal,
            "AGENT_RESULT_REVIEW_REQUIRED",
            "result_report",
            report.id,
            None,
            {"reason": message},
            source="AGENT",
        )
        await session.commit()
        return 202, {"status": "REVIEW_REQUIRED", "run_id": run.id, "report_id": report.id, "message": message}


async def _create_report(
    session: AsyncSession,
    run: AgentRun,
    principal: Principal,
    data: AgentResultIn,
    home: int,
    away: int,
    report_status: ReportStatus,
    reason: str | None,
) -> ResultReport:
    match = await session.get(Match, data.match_id)
    assert match is not None and match.home_team_id is not None and match.away_team_id is not None
    report = ResultReport(
        match_id=data.match_id,
        agent_run_id=run.id,
        agent_label=principal.label[:120],
        home_score=home,
        away_score=away,
        winner_team_id=match.home_team_id if home > away else match.away_team_id,
        source=data.source,
        source_url=data.source_url,
        reported_at=_ensure_utc(data.timestamp),
        extra_sources=[s.model_dump() for s in data.sources] or None,
        status=report_status,
        review_reason=reason,
    )
    session.add(report)
    await session.flush()
    return report


async def _process_valid_result(
    session: AsyncSession, principal: Principal, data: AgentResultIn, payload: Any, force_review: str | None = None
) -> tuple[int, dict[str, Any]]:
    settings = get_settings()
    now = now_utc()
    match = (
        (await session.execute(select(Match).where(Match.id == data.match_id).with_for_update(of=Match)))
        .unique()
        .scalar_one_or_none()
    )
    if match is None:
        raise AgentReject("Match existiert nicht.", status.HTTP_404_NOT_FOUND)
    if not match.teams_known:
        raise AgentReject("Für dieses Match stehen noch keine Teams fest.")
    if match.status == MatchStatus.VOID:
        raise AgentReject("Das Match ist annulliert (VOID).", status.HTTP_409_CONFLICT)

    home, away = data.home_score, data.away_score
    notes: list[str] = []
    # Do the teams match?
    if data.home_team is not None or data.away_team is not None:
        straight = (data.home_team is None or team_matches(data.home_team, match.home_team)) and (
            data.away_team is None or team_matches(data.away_team, match.away_team)
        )
        swapped = (data.home_team is None or team_matches(data.home_team, match.away_team)) and (
            data.away_team is None or team_matches(data.away_team, match.home_team)
        )
        if not straight and swapped:
            home, away = away, home
            notes.append("Heim/Auswärts waren vertauscht und wurden korrigiert.")
        elif not straight:
            raise AgentReject(
                f"Teams stimmen nicht: erwartet {match.home_team.abbreviation} vs {match.away_team.abbreviation}."
            )
    # Is the result plausible?
    if home == away:
        raise AgentReject("Unplausibel: Playoff-Spiele enden nicht unentschieden.")
    winner_team = match.home_team if home > away else match.away_team
    if data.winner is not None and not team_matches(data.winner, winner_team):
        raise AgentReject("Unplausibel: Der gemeldete Sieger passt nicht zum Spielstand.")
    reported_at = _ensure_utc(data.timestamp)
    if reported_at is not None and reported_at > now + timedelta(minutes=10):
        raise AgentReject("Unplausibel: Zeitstempel liegt in der Zukunft.")
    if match.kickoff_at is not None:
        earliest_end = match.kickoff_at + timedelta(minutes=settings.agent_result_min_minutes_after_kickoff)
        if now < earliest_end:
            raise AgentReject("Unplausibel: Das Spiel kann noch nicht beendet sein.", status.HTTP_409_CONFLICT)
        if reported_at is not None and reported_at < match.kickoff_at:
            raise AgentReject("Unplausibel: Zeitstempel liegt vor dem Kickoff.")
    elif match.status == MatchStatus.OPEN and not is_locked(match, now):
        raise AgentReject("Das Spiel ist noch offen und hat keinen Kickoff-Termin.", status.HTTP_409_CONFLICT)

    run = _new_run(principal, "RESULT", payload)
    run.match_id = match.id
    session.add(run)
    await session.flush()

    async def finish(
        run_status: AgentRunStatus, report_status: ReportStatus, message: str, code: int, notify: bool = False
    ) -> tuple[int, dict[str, Any]]:
        full = " ".join([message, *notes]).strip()
        report = await _create_report(
            session,
            run,
            principal,
            data,
            home,
            away,
            report_status,
            full if report_status != ReportStatus.APPLIED else None,
        )
        run.status = run_status
        run.message = full
        run.finished_at = now_utc()
        if notify:
            await notify_admins(
                session, "REVIEW_REQUIRED", f"ChatGPT-Ergebnis prüfen: {match_label(match)}", full, "/admin?tab=agent"
            )
        audit(
            session,
            principal,
            f"AGENT_RESULT_{report_status.value}",
            "result_report",
            report.id,
            None,
            {
                "match_id": match.id,
                "home_score": home,
                "away_score": away,
                "source": data.source,
                "source_url": data.source_url,
                "message": full,
            },
            source="AGENT",
        )
        await session.commit()
        return code, {"status": run_status.value, "run_id": run.id, "report_id": report.id, "message": full}

    # Was the match already evaluated?
    if match.status == MatchStatus.FINAL:
        if (match.home_score, match.away_score) == (home, away):
            return await finish(
                AgentRunStatus.DUPLICATE, ReportStatus.DUPLICATE, "Ergebnis ist bereits gewertet (identisch).", 200
            )
        return await finish(
            AgentRunStatus.REVIEW_REQUIRED,
            ReportStatus.REVIEW_REQUIRED,
            f"Abweichung zum gewerteten Ergebnis {match.home_score}:{match.away_score}.",
            202,
            True,
        )

    if force_review:
        return await finish(AgentRunStatus.REVIEW_REQUIRED, ReportStatus.REVIEW_REQUIRED, force_review, 202, True)

    # Source validation
    if not is_trusted(data.source_url):
        return await finish(
            AgentRunStatus.REVIEW_REQUIRED,
            ReportStatus.REVIEW_REQUIRED,
            f"Quelle nicht vertrauenswürdig oder ohne URL ({domain_of(data.source_url) or '–'}).",
            202,
            True,
        )
    conflicting = [s for s in data.sources if (s.home_score, s.away_score) != (data.home_score, data.away_score)]
    if conflicting:
        names = ", ".join(s.source for s in conflicting)
        return await finish(
            AgentRunStatus.REVIEW_REQUIRED,
            ReportStatus.REVIEW_REQUIRED,
            f"Widersprüchliche Quellen: {names}.",
            202,
            True,
        )
    open_reports = list(
        (
            await session.execute(
                select(ResultReport).where(
                    ResultReport.match_id == match.id,
                    ResultReport.status.in_([ReportStatus.PENDING_CONFIRMATION, ReportStatus.REVIEW_REQUIRED]),
                )
            )
        )
        .unique()
        .scalars()
    )
    if any((r.home_score, r.away_score) != (home, away) for r in open_reports):
        return await finish(
            AgentRunStatus.REVIEW_REQUIRED,
            ReportStatus.REVIEW_REQUIRED,
            "Widerspricht einer früheren Meldung für dieses Spiel.",
            202,
            True,
        )

    # Confirmations from distinct trusted domains
    domains = {domain_of(data.source_url)}
    domains.update(domain_of(s.source_url) for s in data.sources if is_trusted(s.source_url))
    domains.update(domain_of(r.source_url) for r in open_reports if is_trusted(r.source_url))
    domains.discard(None)
    if len(domains) < settings.agent_min_confirmations:
        return await finish(
            AgentRunStatus.PENDING_CONFIRMATION,
            ReportStatus.PENDING_CONFIRMATION,
            f"Warte auf Bestätigung ({len(domains)}/{settings.agent_min_confirmations} Quellen).",
            202,
        )

    await apply_result(
        session,
        match.id,
        home,
        away,
        principal,
        ResultSource.AGENT,
        {"source": data.source, "source_url": data.source_url},
    )
    for r in open_reports:
        r.status = ReportStatus.SUPERSEDED
    return await finish(AgentRunStatus.APPLIED, ReportStatus.APPLIED, "Ergebnis übernommen und ausgewertet.", 200)


async def accept_report(session: AsyncSession, principal: Principal, report_id: int) -> ResultReport:
    report = await session.get(ResultReport, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meldung nicht gefunden")
    if report.status not in (ReportStatus.REVIEW_REQUIRED, ReportStatus.PENDING_CONFIRMATION):
        raise HTTPException(status.HTTP_409_CONFLICT, "Diese Meldung ist bereits erledigt.")
    await apply_result(
        session,
        report.match_id,
        report.home_score,
        report.away_score,
        principal,
        ResultSource.AGENT,
        {"report_id": report.id, "source": report.source, "source_url": report.source_url, "approved_by_admin": True},
    )
    report.status = ReportStatus.APPLIED
    report.reviewed_by = principal.user_id
    report.reviewed_at = now_utc()
    audit(
        session,
        principal,
        "AGENT_REPORT_ACCEPTED",
        "result_report",
        report.id,
        None,
        {"home_score": report.home_score, "away_score": report.away_score},
        source="ADMIN",
    )
    await session.commit()
    return report


async def reject_report(session: AsyncSession, principal: Principal, report_id: int) -> ResultReport:
    report = await session.get(ResultReport, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meldung nicht gefunden")
    if report.status not in (ReportStatus.REVIEW_REQUIRED, ReportStatus.PENDING_CONFIRMATION):
        raise HTTPException(status.HTTP_409_CONFLICT, "Diese Meldung ist bereits erledigt.")
    report.status = ReportStatus.REJECTED
    report.reviewed_by = principal.user_id
    report.reviewed_at = now_utc()
    audit(session, principal, "AGENT_REPORT_REJECTED", "result_report", report.id, None, None, source="ADMIN")
    await session.commit()
    return report


def pending_match_filter(now: datetime):
    """Matches that need a result: teams known, not final/void, kickoff passed or locked."""
    return (
        Match.home_team_id.is_not(None)
        & Match.away_team_id.is_not(None)
        & Match.status.in_([MatchStatus.OPEN, MatchStatus.LOCKED])
        & ((Match.kickoff_at <= now) | (Match.status == MatchStatus.LOCKED))
    ) | Match.result_check_requested_at.is_not(None)


async def request_result_check(
    session: AsyncSession, principal: Principal, match_ids: list[int] | None
) -> dict[str, Any]:
    """Admin action 'Jetzt prüfen': flag matches; the result agent researches them on its next tick."""
    now = now_utc()
    stmt = select(Match)
    stmt = stmt.where(Match.id.in_(match_ids)) if match_ids else stmt.where(pending_match_filter(now))
    matches = [m for m in (await session.execute(stmt)).unique().scalars() if m.teams_known]
    for m in matches:
        m.result_check_requested_at = now
    run = AgentRun(
        agent_label=f"admin:{principal.label}"[:120],
        kind="CHECK_REQUEST",
        status=AgentRunStatus.OK,
        request_payload={"match_ids": [m.id for m in matches]},
        ip_address=principal.ip,
    )
    run.message = f"{len(matches)} Spiel(e) zur Prüfung durch ChatGPT markiert."
    run.finished_at = now_utc()
    session.add(run)
    audit(
        session,
        principal,
        "RESULT_CHECK_REQUESTED",
        "agent_run",
        None,
        None,
        {"match_ids": [m.id for m in matches]},
        source="ADMIN",
    )
    await session.commit()
    return {"matches": len(matches), "message": run.message, "run_id": run.id}
