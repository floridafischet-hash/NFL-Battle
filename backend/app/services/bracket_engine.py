"""Pure NFL playoff bracket logic (no database access).

Every season has 13 slots. Wild Card pairings are 2v7, 3v6, 4v5 per conference (seed 1 has a bye).
After the Wild Card round the NFL re-seeds: seed 1 hosts the lowest remaining seed, the other two
winners play each other. Conference winners meet in the Super Bowl.

The engine resolves a "living bracket" for one user: for every slot it determines the two teams
(actual pairing if known, otherwise derived from the effective winners of the feeder slots), checks
whether the user's pick is still valid and computes the effective winner that advances.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from app.models.enums import Conference, MatchStatus, Round

CONFERENCES: tuple[Conference, Conference] = (Conference.AFC, Conference.NFC)
BYE = "BYE"
UNKNOWN_SEED = 99


@dataclass(frozen=True)
class SlotDef:
    slot: str
    round: Round
    conference: Conference | None
    order: int
    feeders: tuple[str, ...] = ()


def _build_slots() -> dict[str, SlotDef]:
    slots: list[SlotDef] = []
    order = 0
    for conf in CONFERENCES:
        c = conf.value
        for i in (1, 2, 3):
            slots.append(SlotDef(f"{c}-WC-{i}", Round.WILD_CARD, conf, order))
            order += 1
        wc = (f"{c}-WC-1", f"{c}-WC-2", f"{c}-WC-3")
        slots.append(SlotDef(f"{c}-DIV-1", Round.DIVISIONAL, conf, order, wc))
        slots.append(SlotDef(f"{c}-DIV-2", Round.DIVISIONAL, conf, order + 1, wc))
        order += 2
        slots.append(SlotDef(f"{c}-CONF", Round.CONFERENCE, conf, order, (f"{c}-DIV-1", f"{c}-DIV-2")))
        order += 1
    slots.append(SlotDef("SB", Round.SUPER_BOWL, None, order, ("AFC-CONF", "NFC-CONF")))
    return {s.slot: s for s in slots}


SLOTS: dict[str, SlotDef] = _build_slots()
ROUND_ORDER: tuple[Round, ...] = (Round.WILD_CARD, Round.DIVISIONAL, Round.CONFERENCE, Round.SUPER_BOWL)
ROUND_LABELS = {
    Round.WILD_CARD: "Wild Card",
    Round.DIVISIONAL: "Divisional Round",
    Round.CONFERENCE: "Conference Championship",
    Round.SUPER_BOWL: "Super Bowl",
}
WILD_CARD_SEEDS: dict[int, tuple[int, int]] = {1: (2, 7), 2: (3, 6), 3: (4, 5)}


def slots_in_resolution_order() -> list[SlotDef]:
    return sorted(SLOTS.values(), key=lambda s: (ROUND_ORDER.index(s.round), s.order))


def wild_card_slot(conference: Conference, index: int) -> str:
    return f"{conference.value}-WC-{index}"


@dataclass(frozen=True)
class TeamSeed:
    team_id: int
    conference: Conference
    seed: int | None


@dataclass(frozen=True)
class MatchState:
    slot: str
    home_team_id: int | None
    away_team_id: int | None
    status: MatchStatus
    winner_team_id: int | None
    locked: bool

    @property
    def teams_known(self) -> bool:
        return self.home_team_id is not None and self.away_team_id is not None


@dataclass(frozen=True)
class Pick:
    winner_team_id: int
    winner_score: int | None = None
    loser_score: int | None = None


@dataclass
class ResolvedSlot:
    slot: str
    round: Round
    conference: Conference | None
    home_team_id: int | None = None
    away_team_id: int | None = None
    teams_source: str = "none"  # actual | predicted | partial | none
    home_origin: str | None = None  # feeder slot or BYE
    away_origin: str | None = None
    status: MatchStatus = MatchStatus.OPEN
    locked: bool = False
    actual_winner_team_id: int | None = None
    pick: Pick | None = None
    pick_state: str = "none"  # none | valid | pending (pairing still open, team can get there) | invalid
    effective_winner_team_id: int | None = None
    extra: dict = field(default_factory=dict)

    @property
    def teams_known(self) -> bool:
        return self.home_team_id is not None and self.away_team_id is not None

    @property
    def pickable(self) -> bool:
        return self.teams_known and not self.locked


class SeedBook:
    """Seed lookup for the participants of a season."""

    def __init__(self, seeds: Iterable[TeamSeed]):
        self._by_team = {s.team_id: s for s in seeds}

    def seed(self, team_id: int | None) -> int:
        if team_id is None:
            return UNKNOWN_SEED
        info = self._by_team.get(team_id)
        return info.seed if info and info.seed is not None else UNKNOWN_SEED

    def team_with_seed(self, conference: Conference, seed: int) -> int | None:
        for info in self._by_team.values():
            if info.conference == conference and info.seed == seed:
                return info.team_id
        return None

    def better_first(self, a: int, b: int) -> tuple[int, int]:
        """Return (home, away): the better (lower) seed hosts."""
        return (a, b) if self.seed(a) <= self.seed(b) else (b, a)


def reseed_divisional(
    seeds: SeedBook, bye_team_id: int | None, wild_card_winners: list[int]
) -> tuple[tuple[int | None, int | None], tuple[int | None, int | None]]:
    """NFL re-seeding: seed 1 hosts the lowest remaining seed, the other two play each other."""
    if len(wild_card_winners) != 3:
        return (bye_team_id, None), (None, None)
    ordered = sorted(wild_card_winners, key=seeds.seed)
    lowest = ordered[-1]
    div1 = (bye_team_id, lowest)
    div2 = seeds.better_first(ordered[0], ordered[1])
    return div1, div2


def derive_teams(slot: SlotDef, effective: Mapping[str, int | None], seeds: SeedBook) -> tuple[int | None, int | None]:
    """Teams of a slot derived from the effective winners of its feeder slots."""
    if slot.round == Round.WILD_CARD:
        return (None, None)
    if slot.round == Round.DIVISIONAL:
        assert slot.conference is not None
        bye = seeds.team_with_seed(slot.conference, 1)
        winners = [effective.get(f) for f in slot.feeders]
        known = [w for w in winners if w is not None]
        if len(known) < 3:
            return (bye, None) if slot.slot.endswith("-1") else (None, None)
        div1, div2 = reseed_divisional(seeds, bye, known)
        return div1 if slot.slot.endswith("-1") else div2
    a, b = (effective.get(f) for f in slot.feeders)
    if slot.round == Round.SUPER_BOWL:
        return (a, b)  # AFC champion is the designated home team by default
    if a is None or b is None:
        return (a, b)
    return seeds.better_first(a, b)


def _origin(team_id: int | None, slot: SlotDef, resolved: Mapping[str, ResolvedSlot], seeds: SeedBook) -> str | None:
    if team_id is None:
        return None
    if slot.round == Round.DIVISIONAL and slot.conference is not None:
        if seeds.team_with_seed(slot.conference, 1) == team_id:
            return BYE
    for feeder in slot.feeders:
        r = resolved.get(feeder)
        if r and team_id in (r.home_team_id, r.away_team_id):
            return feeder
    return None


def resolve_bracket(
    seeds: Iterable[TeamSeed],
    matches: Mapping[str, MatchState],
    picks: Mapping[str, Pick],
) -> dict[str, ResolvedSlot]:
    """Resolve all 13 slots for one user's picks against the actual state."""
    book = SeedBook(seeds)
    resolved: dict[str, ResolvedSlot] = {}
    effective: dict[str, int | None] = {}
    # teams that can still come out of a slot (used to tell "pending" from "invalid" picks)
    candidates: dict[str, set[int]] = {}

    for slot in slots_in_resolution_order():
        m = matches.get(slot.slot)
        r = ResolvedSlot(slot=slot.slot, round=slot.round, conference=slot.conference)
        if m is not None:
            r.status = m.status
            r.locked = m.locked
            if m.status == MatchStatus.FINAL:
                r.actual_winner_team_id = m.winner_team_id

        if m is not None and m.teams_known:
            r.home_team_id, r.away_team_id = m.home_team_id, m.away_team_id
            r.teams_source = "actual"
        else:
            home, away = derive_teams(slot, effective, book)
            r.home_team_id, r.away_team_id = home, away
            if home is not None and away is not None:
                r.teams_source = "predicted"
            elif home is not None or away is not None:
                r.teams_source = "partial"

        r.home_origin = _origin(r.home_team_id, slot, resolved, book)
        r.away_origin = _origin(r.away_team_id, slot, resolved, book)

        known = {t for t in (r.home_team_id, r.away_team_id) if t is not None}
        reachable = set(known)
        if not r.teams_known:
            for feeder in slot.feeders:
                reachable |= candidates.get(feeder, set())

        pick = picks.get(slot.slot)
        r.pick = pick
        if pick is not None:
            if r.teams_known:
                r.pick_state = "valid" if pick.winner_team_id in known else "invalid"
            else:
                r.pick_state = "pending" if pick.winner_team_id in reachable else "invalid"

        if r.actual_winner_team_id is not None:
            r.effective_winner_team_id = r.actual_winner_team_id
        elif r.status != MatchStatus.VOID and r.pick_state == "valid" and pick is not None:
            r.effective_winner_team_id = pick.winner_team_id
        effective[slot.slot] = r.effective_winner_team_id
        candidates[slot.slot] = {r.effective_winner_team_id} if r.effective_winner_team_id else reachable
        resolved[slot.slot] = r
    return resolved


def picks_to_clear_after_change(resolved: Mapping[str, ResolvedSlot]) -> list[str]:
    """Open picks that became invalid because an upstream pick changed (cascade).

    Picks in slots whose actual pairing is already known are kept (shown as "eliminated") so the
    user sees what they predicted; only hypothetical (predicted/partial) slots are cleaned up.
    """
    return [
        r.slot
        for r in resolved.values()
        if r.pick is not None and r.pick_state == "invalid" and r.teams_source != "actual" and not r.locked
    ]


def actual_advancements(
    seeds: Iterable[TeamSeed], matches: Mapping[str, MatchState]
) -> dict[str, tuple[int | None, int | None]]:
    """Pairings of later rounds that follow from FINAL results only.

    Returns, for every non-wild-card slot whose feeders are all decided, the pairing the actual
    match should have. Used to fill the next round automatically.
    """
    book = SeedBook(seeds)
    effective: dict[str, int | None] = {}
    result: dict[str, tuple[int | None, int | None]] = {}
    for slot in slots_in_resolution_order():
        m = matches.get(slot.slot)
        if slot.round != Round.WILD_CARD:
            home, away = derive_teams(slot, effective, book)
            if home is not None and away is not None:
                result[slot.slot] = (home, away)
        winner = m.winner_team_id if m is not None and m.status == MatchStatus.FINAL else None
        effective[slot.slot] = winner
    return result


def round_complete(matches: Mapping[str, MatchState], round_: Round, conference: Conference | None) -> bool:
    relevant = [
        m
        for s, m in matches.items()
        if SLOTS[s].round == round_ and (conference is None or SLOTS[s].conference == conference)
    ]
    return bool(relevant) and all(m.status == MatchStatus.FINAL for m in relevant)


def downstream_slots(slot: str) -> list[str]:
    """All slots that (transitively) depend on the given slot."""
    out: list[str] = []
    frontier = [slot]
    while frontier:
        current = frontier.pop()
        for s in SLOTS.values():
            if current in s.feeders and s.slot not in out:
                out.append(s.slot)
                frontier.append(s.slot)
    return out
