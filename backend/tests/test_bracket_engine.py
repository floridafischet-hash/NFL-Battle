from app.models.enums import Conference, MatchStatus, Round
from app.services.bracket_engine import (
    BYE,
    SLOTS,
    MatchState,
    Pick,
    TeamSeed,
    actual_advancements,
    downstream_slots,
    picks_to_clear_after_change,
    resolve_bracket,
    round_complete,
)

# Team ids: AFC seeds 1..7 -> 101..107, NFC seeds 1..7 -> 201..207
SEEDS = [TeamSeed(100 + s, Conference.AFC, s) for s in range(1, 8)] + [
    TeamSeed(200 + s, Conference.NFC, s) for s in range(1, 8)
]


def a(seed: int) -> int:
    return 100 + seed


def n(seed: int) -> int:
    return 200 + seed


def wild_card_matches(**overrides: MatchState) -> dict[str, MatchState]:
    matches: dict[str, MatchState] = {}
    for conf, base in (("AFC", 100), ("NFC", 200)):
        for i, (h, w) in {1: (2, 7), 2: (3, 6), 3: (4, 5)}.items():
            slot = f"{conf}-WC-{i}"
            matches[slot] = MatchState(slot, base + h, base + w, MatchStatus.OPEN, None, False)
    for slot in SLOTS:
        matches.setdefault(slot, MatchState(slot, None, None, MatchStatus.OPEN, None, False))
    matches.update(overrides)
    return matches


def final(slot: str, home: int, away: int, winner: int) -> MatchState:
    return MatchState(slot, home, away, MatchStatus.FINAL, winner, True)


def test_slot_layout_has_13_games():
    assert len(SLOTS) == 13
    assert sum(1 for s in SLOTS.values() if s.round == Round.WILD_CARD) == 6
    assert sum(1 for s in SLOTS.values() if s.round == Round.DIVISIONAL) == 4
    assert sum(1 for s in SLOTS.values() if s.round == Round.CONFERENCE) == 2
    assert SLOTS["SB"].feeders == ("AFC-CONF", "NFC-CONF")


def test_winner_advances_with_nfl_reseeding():
    picks = {"AFC-WC-1": Pick(a(2)), "AFC-WC-2": Pick(a(3)), "AFC-WC-3": Pick(a(4))}
    r = resolve_bracket(SEEDS, wild_card_matches(), picks)
    # seed 1 hosts lowest remaining seed (4); 2 hosts 3
    assert (r["AFC-DIV-1"].home_team_id, r["AFC-DIV-1"].away_team_id) == (a(1), a(4))
    assert (r["AFC-DIV-2"].home_team_id, r["AFC-DIV-2"].away_team_id) == (a(2), a(3))
    assert r["AFC-DIV-1"].teams_source == "predicted"
    assert r["AFC-DIV-1"].home_origin == BYE
    assert r["AFC-DIV-1"].away_origin == "AFC-WC-3"


def test_upset_changes_divisional_pairings():
    picks = {"AFC-WC-1": Pick(a(7)), "AFC-WC-2": Pick(a(3)), "AFC-WC-3": Pick(a(5))}
    r = resolve_bracket(SEEDS, wild_card_matches(), picks)
    assert (r["AFC-DIV-1"].home_team_id, r["AFC-DIV-1"].away_team_id) == (a(1), a(7))
    assert (r["AFC-DIV-2"].home_team_id, r["AFC-DIV-2"].away_team_id) == (a(3), a(5))


def test_full_path_valid_picks():
    picks = {
        "AFC-WC-1": Pick(a(2)),
        "AFC-WC-2": Pick(a(3)),
        "AFC-WC-3": Pick(a(4)),
        "AFC-DIV-1": Pick(a(1)),
        "AFC-DIV-2": Pick(a(3)),
        "AFC-CONF": Pick(a(3)),
        "NFC-WC-1": Pick(n(7)),
        "NFC-WC-2": Pick(n(3)),
        "NFC-WC-3": Pick(n(4)),
        "NFC-DIV-1": Pick(n(7)),
        "NFC-DIV-2": Pick(n(3)),
        "NFC-CONF": Pick(n(7)),
        "SB": Pick(n(7)),
    }
    r = resolve_bracket(SEEDS, wild_card_matches(), picks)
    assert all(slot.pick_state == "valid" for slot in r.values())
    assert (r["SB"].home_team_id, r["SB"].away_team_id) == (a(3), n(7))
    assert r["SB"].effective_winner_team_id == n(7)
    assert r["SB"].home_origin == "AFC-CONF" and r["SB"].away_origin == "NFC-CONF"


def test_changing_upstream_pick_cascades():
    picks = {
        "AFC-WC-1": Pick(a(2)),
        "AFC-WC-2": Pick(a(3)),
        "AFC-WC-3": Pick(a(4)),
        "AFC-DIV-1": Pick(a(4)),
        "AFC-DIV-2": Pick(a(2)),
        "AFC-CONF": Pick(a(4)),
    }
    # user switches WC-3 to the 5 seed -> picks with the 4 seed downstream become invalid
    picks["AFC-WC-3"] = Pick(a(5))
    r = resolve_bracket(SEEDS, wild_card_matches(), picks)
    assert set(picks_to_clear_after_change(r)) == {"AFC-DIV-1", "AFC-CONF"}
    assert r["AFC-DIV-2"].pick_state == "valid"


def test_actual_pairing_overrides_prediction_and_marks_busted_pick():
    matches = wild_card_matches(
        **{
            "AFC-WC-1": final("AFC-WC-1", a(2), a(7), a(7)),
            "AFC-WC-2": final("AFC-WC-2", a(3), a(6), a(3)),
            "AFC-WC-3": final("AFC-WC-3", a(4), a(5), a(4)),
            "AFC-DIV-1": MatchState("AFC-DIV-1", a(1), a(7), MatchStatus.OPEN, None, False),
            "AFC-DIV-2": MatchState("AFC-DIV-2", a(3), a(4), MatchStatus.OPEN, None, False),
        }
    )
    picks = {"AFC-WC-1": Pick(a(2)), "AFC-DIV-2": Pick(a(2))}
    r = resolve_bracket(SEEDS, matches, picks)
    assert r["AFC-DIV-2"].teams_source == "actual"
    assert r["AFC-DIV-2"].pick_state == "invalid"
    # busted picks in actual pairings are kept, not cascaded away
    assert "AFC-DIV-2" not in picks_to_clear_after_change(r)
    assert r["AFC-WC-1"].effective_winner_team_id == a(7)  # actual result wins over the pick


def test_actual_advancements_follow_results():
    matches = wild_card_matches(
        **{
            "AFC-WC-1": final("AFC-WC-1", a(2), a(7), a(2)),
            "AFC-WC-2": final("AFC-WC-2", a(3), a(6), a(6)),
            "AFC-WC-3": final("AFC-WC-3", a(4), a(5), a(5)),
        }
    )
    adv = actual_advancements(SEEDS, matches)
    assert adv["AFC-DIV-1"] == (a(1), a(6))
    assert adv["AFC-DIV-2"] == (a(2), a(5))
    assert "NFC-DIV-1" not in adv
    assert round_complete(matches, Round.WILD_CARD, Conference.AFC)
    assert not round_complete(matches, Round.WILD_CARD, Conference.NFC)


def test_partial_wild_card_results_leave_divisional_open():
    matches = wild_card_matches(**{"AFC-WC-1": final("AFC-WC-1", a(2), a(7), a(2))})
    adv = actual_advancements(SEEDS, matches)
    assert "AFC-DIV-1" not in adv and "AFC-DIV-2" not in adv


def test_downstream_slots():
    assert set(downstream_slots("AFC-WC-2")) == {"AFC-DIV-1", "AFC-DIV-2", "AFC-CONF", "SB"}
    assert downstream_slots("SB") == []


def test_void_match_has_no_effective_winner():
    matches = wild_card_matches(**{"AFC-WC-1": MatchState("AFC-WC-1", a(2), a(7), MatchStatus.VOID, None, True)})
    r = resolve_bracket(SEEDS, matches, {"AFC-WC-1": Pick(a(2))})
    assert r["AFC-WC-1"].effective_winner_team_id is None


def test_pick_waiting_for_opponent_is_pending_not_invalid():
    # AFC side fully picked, NFC conference still open -> Super Bowl pick of the AFC champion is pending
    picks = {
        "AFC-WC-1": Pick(a(2)),
        "AFC-WC-2": Pick(a(3)),
        "AFC-WC-3": Pick(a(4)),
        "AFC-DIV-1": Pick(a(1)),
        "AFC-DIV-2": Pick(a(3)),
        "AFC-CONF": Pick(a(1)),
        "SB": Pick(a(1)),
    }
    r = resolve_bracket(SEEDS, wild_card_matches(), picks)
    assert r["SB"].teams_source == "partial"
    assert r["SB"].pick_state == "pending"
    assert "SB" not in picks_to_clear_after_change(r)
    # a team that cannot reach the slot anymore is invalid
    picks["SB"] = Pick(a(4))
    picks["AFC-CONF"] = Pick(a(1))
    r = resolve_bracket(SEEDS, wild_card_matches(), picks)
    assert r["SB"].pick_state == "invalid"
