from __future__ import annotations

from typing import Any

from app.models import PredictionChange
from app.services.seasons import match_out, team_out


def change_request_out(cr: PredictionChange) -> dict[str, Any]:
    return {
        "id": cr.id,
        "status": cr.status.value,
        "match_id": cr.match_id,
        "slot": cr.match.slot,
        "user": {"id": cr.user.id, "display_name": cr.user.display_name, "avatar_url": cr.user.avatar_url},
        "old": None
        if cr.old_winner_team_id is None
        else {
            "winner_team_id": cr.old_winner_team_id,
            "winner_score": cr.old_winner_score,
            "loser_score": cr.old_loser_score,
            "winner_team": team_out(cr.old_winner_team),
        },
        "new": {
            "winner_team_id": cr.new_winner_team_id,
            "winner_score": cr.new_winner_score,
            "loser_score": cr.new_loser_score,
            "winner_team": team_out(cr.new_winner_team),
        },
        "reason": cr.reason,
        "created_at": cr.created_at,
        "decided_at": cr.decided_at,
        "decided_by": cr.decider.display_name if cr.decider else None,
        "decision_note": cr.decision_note,
        "match": match_out(cr.match),
    }
