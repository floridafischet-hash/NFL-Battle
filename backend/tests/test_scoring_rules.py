from app.services.bracket_engine import Pick
from app.services.scoring_rules import (
    ActualResult,
    ScoringConfig,
    StandingInput,
    best_streak,
    competition_ranks,
    score_pick,
)

CFG = ScoringConfig(winner_points=1, exact_score_points=3, champion_bonus=3, score_tips_enabled=True)
RESULT = ActualResult(winner_team_id=1, winner_score=31, loser_score=24)


def test_correct_winner_scores_winner_points():
    s = score_pick(Pick(1, 27, 20), RESULT, CFG)
    assert (s.winner_correct, s.exact_correct, s.points) == (True, False, 1)


def test_exact_score_replaces_winner_points():
    s = score_pick(Pick(1, 31, 24), RESULT, CFG)
    assert (s.winner_correct, s.exact_correct, s.points) == (True, True, 3)


def test_wrong_winner_scores_nothing_even_with_matching_numbers():
    s = score_pick(Pick(2, 31, 24), RESULT, CFG)
    assert (s.winner_correct, s.exact_correct, s.points) == (False, False, 0)


def test_missing_pick():
    s = score_pick(None, RESULT, CFG)
    assert not s.has_pick and s.points == 0


def test_super_bowl_bonus():
    sb = ActualResult(winner_team_id=1, winner_score=31, loser_score=24, is_super_bowl=True)
    assert score_pick(Pick(1), sb, CFG).points == 1 + 3
    assert score_pick(Pick(1, 31, 24), sb, CFG).points == 3 + 3
    assert score_pick(Pick(2), sb, CFG).points == 0


def test_score_tips_disabled_ignores_exact():
    cfg = ScoringConfig(score_tips_enabled=False)
    assert score_pick(Pick(1, 31, 24), RESULT, cfg).points == 1


def test_configurable_points():
    cfg = ScoringConfig(winner_points=2, exact_score_points=5, champion_bonus=10)
    assert score_pick(Pick(1, 31, 24), RESULT, cfg).points == 5
    assert score_pick(Pick(1), RESULT, cfg).points == 2


def test_competition_ranking_shares_ranks():
    entries = [
        StandingInput("a", 10, 1, 8, "a"),
        StandingInput("b", 12, 0, 9, "b"),
        StandingInput("c", 10, 1, 8, "c"),
        StandingInput("d", 10, 0, 9, "d"),
    ]
    ranked = {e.key: r for e, r in competition_ranks(entries)}
    assert ranked == {"b": 1, "a": 2, "c": 2, "d": 4}


def test_streaks():
    assert best_streak([True, True, False, True, True, True, False, True]) == (3, 1)
    assert best_streak([]) == (0, 0)
