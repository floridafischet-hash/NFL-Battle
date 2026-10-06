"""Pure scoring rules (no database access)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.bracket_engine import Pick


@dataclass(frozen=True)
class ScoringConfig:
    winner_points: int = 1
    exact_score_points: int = 3
    champion_bonus: int = 3
    score_tips_enabled: bool = True


@dataclass(frozen=True)
class ActualResult:
    winner_team_id: int
    winner_score: int
    loser_score: int
    is_super_bowl: bool = False


@dataclass(frozen=True)
class PickScore:
    has_pick: bool
    winner_correct: bool
    exact_correct: bool
    base_points: int
    bonus_points: int

    @property
    def points(self) -> int:
        return self.base_points + self.bonus_points


def score_pick(pick: Pick | None, actual: ActualResult, config: ScoringConfig) -> PickScore:
    """Points for one prediction.

    * correct winner                 -> winner_points
    * correct winner + exact score   -> max(winner_points, exact_score_points)  (replaces winner points)
    * Super Bowl winner correct      -> + champion_bonus
    """
    if pick is None:
        return PickScore(False, False, False, 0, 0)
    winner_correct = pick.winner_team_id == actual.winner_team_id
    exact_correct = (
        winner_correct
        and config.score_tips_enabled
        and pick.winner_score is not None
        and pick.loser_score is not None
        and pick.winner_score == actual.winner_score
        and pick.loser_score == actual.loser_score
    )
    if exact_correct:
        base = max(config.winner_points, config.exact_score_points)
    elif winner_correct:
        base = config.winner_points
    else:
        base = 0
    bonus = config.champion_bonus if (actual.is_super_bowl and winner_correct) else 0
    return PickScore(True, winner_correct, exact_correct, base, bonus)


@dataclass
class StandingInput:
    key: object
    points: int
    exact_scores: int
    correct_winners: int
    name: str = ""


def competition_ranks(entries: list[StandingInput]) -> list[tuple[StandingInput, int]]:
    """Sort by points, exact scores, correct winners (desc). Ties share the rank (1, 2, 2, 4)."""
    ordered = sorted(entries, key=lambda e: (-e.points, -e.exact_scores, -e.correct_winners, e.name.lower()))
    ranked: list[tuple[StandingInput, int]] = []
    previous: tuple[int, int, int] | None = None
    rank = 0
    for index, entry in enumerate(ordered, start=1):
        signature = (entry.points, entry.exact_scores, entry.correct_winners)
        if signature != previous:
            rank = index
            previous = signature
        ranked.append((entry, rank))
    return ranked


def best_streak(results: list[bool]) -> tuple[int, int]:
    """Return (best streak, current streak) of consecutive correct picks."""
    best = current = 0
    for ok in results:
        current = current + 1 if ok else 0
        best = max(best, current)
    return best, current
