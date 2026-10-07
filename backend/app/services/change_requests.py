"""Change requests for predictions after the tip lock (approved/rejected by an admin)."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.models import Match, Prediction, PredictionChange, Season
from app.models.enums import ChangeRequestStatus, MatchStatus
from app.realtime.events import publish
from app.services.audit import audit
from app.services.bracket_engine import Pick
from app.services.brackets import _apply_cascade, get_or_create_bracket, load_context, pick_dict, picks_by_slot
from app.services.notifications import notify, notify_admins
from app.services.results import lock_season
from app.services.scoring import recompute_leaderboard, score_match
from app.services.seasons import is_locked, match_label, now_utc


def _validate_scores(
    season: Season, winner_score: int | None, loser_score: int | None
) -> tuple[int | None, int | None]:
    if not season.score_tips_enabled:
        return None, None
    if (winner_score is None) != (loser_score is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Bitte beide Punktzahlen angeben.")
    if winner_score is not None and loser_score is not None and winner_score <= loser_score:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Der getippte Sieger muss mehr Punkte haben.")
    return winner_score, loser_score


async def create_request(
    session: AsyncSession,
    principal: Principal,
    match_id: int,
    winner_team_id: int,
    winner_score: int | None,
    loser_score: int | None,
    reason: str | None,
) -> PredictionChange:
    assert principal.user is not None
    match = await session.get(Match, match_id)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Spiel nicht gefunden")
    season = await session.get(Season, match.season_id)
    assert season is not None
    if not is_locked(match):
        raise HTTPException(status.HTTP_409_CONFLICT, "Das Spiel ist noch offen – du kannst deinen Tipp direkt ändern.")
    if match.status in (MatchStatus.FINAL, MatchStatus.VOID):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Für gewertete oder annullierte Spiele sind keine Änderungen möglich."
        )
    if not match.teams_known or winner_team_id not in (match.home_team_id, match.away_team_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Dieses Team spielt nicht in dieser Partie.")
    winner_score, loser_score = _validate_scores(season, winner_score, loser_score)

    bracket = await get_or_create_bracket(session, principal.user.id, season.id)
    current = next((p for p in bracket.predictions if p.match_id == match.id), None)
    if current and (current.winner_team_id, current.winner_score, current.loser_score) == (
        winner_team_id,
        winner_score,
        loser_score,
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Der neue Tipp entspricht deinem aktuellen Tipp.")

    cr = PredictionChange(
        user_id=principal.user.id,
        match_id=match.id,
        old_winner_team_id=current.winner_team_id if current else None,
        old_winner_score=current.winner_score if current else None,
        old_loser_score=current.loser_score if current else None,
        new_winner_team_id=winner_team_id,
        new_winner_score=winner_score,
        new_loser_score=loser_score,
        reason=(reason or "").strip()[:500] or None,
    )
    session.add(cr)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Für dieses Spiel gibt es bereits einen offenen Antrag.")
    audit(
        session,
        principal,
        "CHANGE_REQUEST_CREATED",
        "prediction_change",
        cr.id,
        pick_dict(current),
        {
            "winner_team_id": winner_team_id,
            "winner_score": winner_score,
            "loser_score": loser_score,
            "match_id": match.id,
            "reason": cr.reason,
        },
    )
    await notify_admins(
        session,
        "CHANGE_REQUEST",
        f"Änderungsantrag von {principal.user.display_name}",
        match_label(match),
        "/admin?tab=requests",
    )
    await publish(session, "change_request_updated", target_admins=True)
    await session.commit()
    await session.refresh(cr)
    return cr


async def _load_pending(session: AsyncSession, request_id: int) -> PredictionChange:
    cr = (
        (
            await session.execute(
                select(PredictionChange).where(PredictionChange.id == request_id).with_for_update(of=PredictionChange)
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    if cr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Antrag nicht gefunden")
    if cr.status != ChangeRequestStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Der Antrag wurde bereits bearbeitet.")
    return cr


async def approve(session: AsyncSession, principal: Principal, request_id: int, note: str | None) -> PredictionChange:
    cr = await _load_pending(session, request_id)
    match = cr.match
    season = await lock_season(session, match.season_id)
    if match.status == MatchStatus.VOID:
        raise HTTPException(status.HTTP_409_CONFLICT, "Das Spiel wurde annulliert.")
    if not match.teams_known or cr.new_winner_team_id not in (match.home_team_id, match.away_team_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Der beantragte Tipp passt nicht mehr zur Paarung.")

    ctx = await load_context(session, season)
    bracket = await get_or_create_bracket(session, cr.user_id, season.id, for_update=True)
    pred = next((p for p in bracket.predictions if p.match_id == match.id), None)
    old = pick_dict(pred)
    if pred is None:
        pred = Prediction(bracket_id=bracket.id, match_id=match.id, winner_team_id=cr.new_winner_team_id)
        bracket.predictions.append(pred)
    pred.winner_team_id = cr.new_winner_team_id
    pred.winner_score = cr.new_winner_score
    pred.loser_score = cr.new_loser_score
    pred.updated_via = "CHANGE_REQUEST"
    picks = picks_by_slot(bracket.predictions, ctx.by_id)
    picks[match.slot] = Pick(cr.new_winner_team_id, cr.new_winner_score, cr.new_loser_score)
    await _apply_cascade(session, principal, ctx, bracket, picks)

    cr.status = ChangeRequestStatus.APPROVED
    cr.decided_by = principal.user_id
    cr.decided_at = now_utc()
    cr.decision_note = (note or "").strip()[:500] or None
    await session.flush()
    audit(
        session, principal, "CHANGE_REQUEST_APPROVED", "prediction_change", cr.id, old, pick_dict(pred), source="ADMIN"
    )
    audit(
        session,
        principal,
        "PREDICTION_UPDATED",
        "prediction",
        f"{cr.user_id}:{match.id}",
        old,
        {**(pick_dict(pred) or {}), "via": "CHANGE_REQUEST"},
        source="ADMIN",
    )
    if match.status == MatchStatus.FINAL:
        await score_match(session, season, match)
        await recompute_leaderboard(session, season)
    await notify(
        session,
        [cr.user_id],
        "CHANGE_REQUEST_APPROVED",
        "Dein Änderungsantrag wurde genehmigt ✅",
        match_label(match),
        f"/spiele/{match.id}",
    )
    await publish(session, "bracket_updated", season_id=season.id, user_id=str(cr.user_id))
    await publish(session, "change_request_updated", target_user_id=str(cr.user_id))
    await session.commit()
    return cr


async def reject(session: AsyncSession, principal: Principal, request_id: int, note: str | None) -> PredictionChange:
    cr = await _load_pending(session, request_id)
    cr.status = ChangeRequestStatus.REJECTED
    cr.decided_by = principal.user_id
    cr.decided_at = now_utc()
    cr.decision_note = (note or "").strip()[:500] or None
    audit(
        session,
        principal,
        "CHANGE_REQUEST_REJECTED",
        "prediction_change",
        cr.id,
        None,
        {"note": cr.decision_note},
        source="ADMIN",
    )
    await notify(
        session,
        [cr.user_id],
        "CHANGE_REQUEST_REJECTED",
        "Dein Änderungsantrag wurde abgelehnt",
        cr.decision_note or match_label(cr.match),
        f"/spiele/{cr.match_id}",
    )
    await publish(session, "change_request_updated", target_user_id=str(cr.user_id))
    await session.commit()
    return cr


async def cancel(session: AsyncSession, principal: Principal, request_id: int) -> None:
    cr = await _load_pending(session, request_id)
    if cr.user_id != principal.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nicht dein Antrag")
    cr.status = ChangeRequestStatus.CANCELLED
    cr.decided_at = now_utc()
    audit(session, principal, "CHANGE_REQUEST_CANCELLED", "prediction_change", cr.id, None, None)
    await session.commit()
