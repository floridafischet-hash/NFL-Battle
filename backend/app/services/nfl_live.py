"""Read-only live NFL team data aggregated from ESPN's public site feeds."""

from __future__ import annotations

import asyncio
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
WEB_BASE = "https://site.web.api.espn.com/apis/common/v3/sports/football/nfl"
TEAM_RE = re.compile(r"^[a-z]{2,3}$")
ATHLETE_RE = re.compile(r"^[0-9]{1,12}$")
NFL_TEAM_SLUGS = frozenset(
    {
        "ari",
        "atl",
        "bal",
        "buf",
        "car",
        "chi",
        "cin",
        "cle",
        "dal",
        "den",
        "det",
        "gb",
        "hou",
        "ind",
        "jax",
        "kc",
        "lv",
        "lac",
        "lar",
        "mia",
        "min",
        "ne",
        "no",
        "nyg",
        "nyj",
        "phi",
        "pit",
        "sea",
        "sf",
        "tb",
        "ten",
        "wsh",
    }
)
CACHE_SECONDS = 300
COMPLETED_GAME_RETENTION_HOURS = 72
_cache: dict[str, tuple[float, Any]] = {}
_lock = asyncio.Lock()


class LiveDataError(RuntimeError):
    pass


async def _fetch_json(url: str, cache_seconds: int = CACHE_SECONDS) -> dict[str, Any]:
    now = time.monotonic()
    cached = _cache.get(url)
    if cached and cached[0] > now:
        return cached[1]
    async with _lock:
        cached = _cache.get(url)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.get(url, headers={"Accept": "application/json"})
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LiveDataError("Aktuelle NFL-Daten sind vorübergehend nicht erreichbar.") from exc
        _cache[url] = (time.monotonic() + cache_seconds, data)
        return data


async def _json(path: str) -> dict[str, Any]:
    return await _fetch_json(f"{BASE}{path}")


def _logo(team: dict[str, Any]) -> str | None:
    return next((x.get("href") for x in team.get("logos", []) if x.get("href")), None)


def _team(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "abbreviation": item.get("abbreviation"),
        "slug": item.get("abbreviation", "").lower(),
        "name": item.get("displayName"),
        "short_name": item.get("shortDisplayName"),
        "location": item.get("location"),
        "color": item.get("color"),
        "alternate_color": item.get("alternateColor"),
        "logo": _logo(item),
    }


async def teams() -> dict[str, Any]:
    data, divisions = await asyncio.gather(_json("/teams"), division_standings())
    rows = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    items = sorted((_team(row.get("team", {})) for row in rows), key=lambda x: x["name"] or "")
    return {"updated_at": data.get("timestamp"), "source": "ESPN", "teams": items, "divisions": divisions}


def _standing_value(stats: dict[str, dict[str, Any]], *names: str) -> str | None:
    for name in names:
        value = stats.get(name, {}).get("displayValue")
        if value is not None:
            return str(value)
    return None


async def division_standings() -> list[dict[str, Any]]:
    """Return all eight divisions and the current team records/statistics."""
    data = await _fetch_json(
        "https://site.api.espn.com/apis/v2/sports/football/nfl/standings"
        "?region=us&lang=en&contentorigin=espn&type=0&level=3&sort=playoffseed%3Aasc"
    )
    divisions: list[dict[str, Any]] = []
    for conference in data.get("children", []):
        conference_name = conference.get("abbreviation")
        if conference_name not in {"AFC", "NFC"}:
            continue
        for division in conference.get("children", []):
            entries = []
            for rank, entry in enumerate(division.get("standings", {}).get("entries", []), start=1):
                team = entry.get("team", {})
                stats = {stat.get("name"): stat for stat in entry.get("stats", [])}
                entries.append(
                    {
                        "rank": rank,
                        "slug": team.get("abbreviation", "").lower(),
                        "name": team.get("displayName"),
                        "short_name": team.get("shortDisplayName"),
                        "abbreviation": team.get("abbreviation"),
                        "logo": _logo(team),
                        "wins": _standing_value(stats, "wins"),
                        "losses": _standing_value(stats, "losses"),
                        "ties": _standing_value(stats, "ties"),
                        "win_percent": _standing_value(stats, "winPercent"),
                        "home": _standing_value(stats, "Home"),
                        "road": _standing_value(stats, "Road"),
                        "division": _standing_value(stats, "divisionRecord", "vs. Div."),
                        "conference": _standing_value(stats, "vs. Conf."),
                        "points_for": _standing_value(stats, "pointsFor"),
                        "points_against": _standing_value(stats, "pointsAgainst"),
                        "differential": _standing_value(stats, "pointDifferential", "differential"),
                        "streak": _standing_value(stats, "streak"),
                    }
                )
            divisions.append(
                {
                    "name": division.get("name"),
                    "abbreviation": division.get("abbreviation"),
                    "conference": conference_name,
                    "teams": entries,
                }
            )
    return divisions


def _scoreboard_team(competitor: dict[str, Any]) -> dict[str, Any]:
    team = competitor.get("team", {})
    overall = next((row for row in competitor.get("records", []) if row.get("name") == "overall"), None)
    return {
        "id": team.get("id"),
        "name": team.get("displayName"),
        "short_name": team.get("shortDisplayName"),
        "abbreviation": team.get("abbreviation"),
        "logo": team.get("logo"),
        "score": _display(competitor.get("score")),
        "record": overall.get("summary") if overall else None,
        "winner": competitor.get("winner"),
    }


def _scoreboard_game(event: dict[str, Any]) -> dict[str, Any] | None:
    competition = (event.get("competitions") or [{}])[0]
    competitors = competition.get("competitors", [])
    home = next((row for row in competitors if row.get("homeAway") == "home"), None)
    away = next((row for row in competitors if row.get("homeAway") == "away"), None)
    if not home or not away:
        return None
    status = competition.get("status", {}).get("type", {})
    return {
        "id": event.get("id"),
        "date": event.get("date"),
        "week": event.get("week", {}).get("number"),
        "season_type": event.get("season", {}).get("type"),
        "state": status.get("state"),
        "completed": bool(status.get("completed")),
        "status": status.get("shortDetail") or status.get("detail") or status.get("description"),
        "venue": competition.get("venue", {}).get("fullName"),
        "home": _scoreboard_team(home),
        "away": _scoreboard_team(away),
    }


async def regular_season_games() -> dict[str, Any]:
    """Current NFL week, limited to regular-season games and refreshed every minute."""
    data = await _fetch_json(f"{BASE}/scoreboard", cache_seconds=60)
    now = datetime.now(UTC)
    season_year = data.get("season", {}).get("year")
    season_type = data.get("season", {}).get("type")
    if season_type != 2 or not season_year:
        return {
            "updated_at": now.isoformat(),
            "source": "ESPN",
            "regular_season": False,
            "season": season_year,
            "week": data.get("week", {}).get("number"),
            "games": [],
        }
    season_data = await _fetch_json(f"{BASE}/scoreboard?dates={season_year}&limit=1000", cache_seconds=60)
    games = [
        game
        for event in season_data.get("events", [])
        if event.get("season", {}).get("type") == 2 and event.get("season", {}).get("year") == season_year
        if (game := _scoreboard_game(event)) is not None
    ]
    upcoming_weeks = [game["week"] for game in games if game["state"] == "pre" and game.get("week") is not None]
    next_week = min(upcoming_weeks, default=None)
    visible_games = []
    for game in games:
        try:
            kickoff = datetime.fromisoformat(str(game.get("date", "")).replace("Z", "+00:00"))
        except ValueError:
            kickoff = now
        if game["completed"] and now - kickoff > timedelta(hours=COMPLETED_GAME_RETENTION_HOURS):
            continue
        if game["state"] == "pre" and next_week is not None and game.get("week") != next_week:
            continue
        game["_kickoff_timestamp"] = kickoff.timestamp()
        visible_games.append(game)

    def order(game: dict[str, Any]) -> tuple[int, float]:
        timestamp = game.pop("_kickoff_timestamp", now.timestamp())
        if game["state"] == "in":
            return (0, timestamp)
        if game["state"] == "pre":
            return (1, timestamp)
        return (2, -timestamp)

    visible_games.sort(key=order)
    return {
        "updated_at": datetime.now(UTC).isoformat(),
        "source": "ESPN",
        "regular_season": True,
        "season": season_year,
        "week": next_week or data.get("week", {}).get("number"),
        "games": visible_games,
    }


async def conference_standings() -> list[dict[str, Any]]:
    """Return the current overall AFC/NFC order (playoff seed)."""
    data = await _fetch_json(
        "https://site.api.espn.com/apis/v2/sports/football/nfl/standings"
        "?region=us&lang=en&contentorigin=espn&type=0&level=2&sort=playoffseed%3Aasc"
    )
    rows: list[dict[str, Any]] = []
    for conference in data.get("children", []):
        conference_name = conference.get("abbreviation")
        if conference_name not in {"AFC", "NFC"}:
            continue
        for fallback_rank, entry in enumerate(conference.get("standings", {}).get("entries", []), start=1):
            team = entry.get("team", {})
            stats = {stat.get("name"): stat for stat in entry.get("stats", [])}
            seed = stats.get("playoffSeed", {}).get("value")
            record = stats.get("overall", {}).get("displayValue")
            rows.append(
                {
                    "slug": team.get("abbreviation", "").lower(),
                    "name": team.get("displayName"),
                    "short_name": team.get("shortDisplayName"),
                    "abbreviation": team.get("abbreviation"),
                    "logo": _logo(team),
                    "conference": conference_name,
                    "rank": int(seed) if isinstance(seed, (int, float)) else fallback_rank,
                    "record": record,
                }
            )
    return rows


def _competitor(comp: dict[str, Any], slug: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    participants = comp.get("competitors", [])
    mine = next((x for x in participants if x.get("team", {}).get("abbreviation", "").lower() == slug), None)
    opponent = next((x for x in participants if x is not mine), None)
    return mine, opponent


def _display(value: Any) -> str | int | float | None:
    """ESPN alternates between scalar values and {value, displayValue} objects."""
    if isinstance(value, dict):
        return value.get("displayValue") if value.get("displayValue") is not None else value.get("value")
    return value if isinstance(value, (str, int, float)) else None


def _game(event: dict[str, Any], slug: str) -> dict[str, Any] | None:
    comp = (event.get("competitions") or [{}])[0]
    mine, opponent = _competitor(comp, slug)
    if not mine or not opponent:
        return None
    status = comp.get("status", {}).get("type", {})
    return {
        "id": event.get("id"),
        "date": event.get("date"),
        "completed": bool(status.get("completed")),
        "status": status.get("shortDetail") or status.get("detail"),
        "home_away": mine.get("homeAway"),
        "team_score": _display(mine.get("score")),
        "opponent_score": _display(opponent.get("score")),
        "won": mine.get("winner"),
        "opponent": {
            "name": opponent.get("team", {}).get("displayName"),
            "abbreviation": opponent.get("team", {}).get("abbreviation"),
            "logo": opponent.get("team", {}).get("logo"),
        },
        "venue": comp.get("venue", {}).get("fullName"),
    }


def _injuries(data: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    group = next((x for x in data.get("injuries", []) if str(x.get("id")) == str(team_id)), {})
    out = []
    for item in group.get("injuries", []):
        athlete = item.get("athlete", {})
        out.append(
            {
                "id": item.get("id"),
                "name": athlete.get("displayName"),
                "position": athlete.get("position", {}).get("abbreviation"),
                "headshot": athlete.get("headshot", {}).get("href"),
                "status": item.get("status") or item.get("type", {}).get("description"),
                "detail": item.get("details", {}).get("type") or item.get("shortComment"),
                "return_date": item.get("details", {}).get("returnDate"),
                "updated_at": item.get("date"),
            }
        )
    return out


def _roster(data: dict[str, Any]) -> list[dict[str, Any]]:
    groups = []
    labels = {
        "offense": "Offense",
        "defense": "Defense",
        "specialTeam": "Special Teams",
        "injuredReserveOrOut": "Injured Reserve / Out",
        "practiceSquad": "Practice Squad",
        "suspended": "Gesperrt",
    }
    for group in data.get("athletes", []):
        players = []
        for player in group.get("items", []):
            players.append(
                {
                    "id": player.get("id"),
                    "name": player.get("displayName"),
                    "jersey": player.get("jersey"),
                    "position": player.get("position", {}).get("abbreviation"),
                    "position_name": player.get("position", {}).get("displayName"),
                    "age": player.get("age"),
                    "experience": player.get("experience", {}).get("years"),
                    "height": player.get("displayHeight"),
                    "weight": player.get("displayWeight"),
                    "headshot": player.get("headshot", {}).get("href"),
                    "status": player.get("status", {}).get("name"),
                }
            )
        if players:
            groups.append(
                {
                    "key": group.get("position"),
                    "label": labels.get(group.get("position"), group.get("position")),
                    "players": players,
                }
            )
    return groups


STAT_LABELS = {
    "gamesPlayed": "Spiele",
    "completions": "Angekommene Pässe",
    "passingAttempts": "Passversuche",
    "completionPct": "Passquote (%)",
    "passingYards": "Pass-Yards",
    "yardsPerPassAttempt": "Yards je Pass",
    "passingTouchdowns": "Pass-Touchdowns",
    "interceptions": "Interceptions",
    "longPassing": "Längster Pass",
    "QBRating": "Passer Rating",
    "adjQBR": "QBR",
    "rushingAttempts": "Laufversuche",
    "rushingYards": "Rush-Yards",
    "yardsPerRushAttempt": "Yards je Lauf",
    "rushingTouchdowns": "Rush-Touchdowns",
    "longRushing": "Längster Lauf",
    "rushingFirstDowns": "First Downs per Lauf",
    "rushingFumbles": "Fumbles nach Lauf",
    "rushingFumblesLost": "Verlorene Fumbles nach Lauf",
    "receptions": "Receptions",
    "receivingTargets": "Targets",
    "receivingYards": "Receiving-Yards",
    "yardsPerReception": "Yards je Catch",
    "receivingTouchdowns": "Receiving-Touchdowns",
    "longReception": "Längster Catch",
    "receivingFirstDowns": "First Downs per Catch",
    "receivingFumbles": "Fumbles nach Catch",
    "receivingFumblesLost": "Verlorene Fumbles nach Catch",
    "totalTackles": "Tackles gesamt",
    "soloTackles": "Solo-Tackles",
    "assistedTackles": "Assistierte Tackles",
    "assistTackles": "Assistierte Tackles",
    "sacks": "Sacks",
    "passesDefended": "Verteidigte Pässe",
    "defensiveInterceptions": "Interceptions",
    "forcedFumbles": "Erzwungene Fumbles",
    "fumblesForced": "Erzwungene Fumbles",
    "fumblesRecovered": "Eroberte Fumbles",
    "fumblesRecoveredYards": "Yards nach Fumble-Eroberung",
    "interceptionYards": "Interception-Yards",
    "avgInterceptionYards": "Ø Interception-Yards",
    "interceptionTouchdowns": "Interception-Touchdowns",
    "longInterception": "Längste Interception",
    "stuffs": "Stops hinter der Linie",
    "stuffYards": "Verhinderte Yards",
    "kicksBlocked": "Geblockte Kicks",
    "fieldGoalsMade": "Field Goals",
    "fieldGoalAttempts": "Field-Goal-Versuche",
    "fieldGoalPct": "Field-Goal-Quote (%)",
    "extraPointsMade": "Extrapunkte",
    "punts": "Punts",
    "puntingYards": "Punt-Yards",
    "grossAvgPuntYards": "Punt-Durchschnitt",
    "returnTouchdowns": "Return-Touchdowns",
    "totalTouchdowns": "Touchdowns gesamt",
    "totalTwoPointConvs": "Two-Point Conversions",
    "kickExtraPoints": "Extrapunkte",
    "fieldGoals": "Field Goals",
    "totalPoints": "Punkte gesamt",
}

CATEGORY_LABELS = {
    "passing": "Passing",
    "rushing": "Rushing",
    "receiving": "Receiving",
    "defensive": "Defense",
    "interceptions": "Interceptions",
    "fumbles": "Fumbles",
    "kicking": "Kicking",
    "punting": "Punting",
    "returning": "Returns",
    "scoring": "Punkte",
}


def _player_categories(data: dict[str, Any], season: int) -> list[dict[str, Any]]:
    groups = []
    for category in data.get("categories", []):
        row = next(
            (item for item in category.get("statistics", []) if item.get("season", {}).get("year") == season), None
        )
        if not row:
            continue
        stats = []
        for index, value in enumerate(row.get("stats", [])):
            if value in (None, "-"):
                continue
            names = category.get("names", [])
            displays = category.get("displayNames", [])
            name = names[index] if index < len(names) else str(index)
            label = STAT_LABELS.get(name, displays[index] if index < len(displays) else name)
            stats.append({"key": name, "label": label, "value": value})
        if stats:
            key = category.get("name") or "other"
            groups.append(
                {"key": key, "label": CATEGORY_LABELS.get(key, category.get("displayName") or key), "stats": stats}
            )
    return groups


async def player_detail(athlete_id: str) -> dict[str, Any]:
    if not ATHLETE_RE.fullmatch(athlete_id):
        raise LiveDataError("Ungültiger Spieler.")
    try:
        overview, stats = await asyncio.gather(
            _fetch_json(f"{WEB_BASE}/athletes/{athlete_id}"),
            _fetch_json(f"{WEB_BASE}/athletes/{athlete_id}/stats"),
        )
    except LiveDataError:
        raise
    athlete = overview.get("athlete", {})
    if str(athlete.get("id")) != athlete_id:
        raise LiveDataError("Spieler nicht gefunden.")
    current_year = datetime.now(UTC).year
    available_years = [
        row.get("season", {}).get("year")
        for category in stats.get("categories", [])
        for row in category.get("statistics", [])
        if isinstance(row.get("season", {}).get("year"), int)
    ]
    season = current_year if current_year in available_years else max(available_years, default=current_year)
    summary = athlete.get("statsSummary", {})
    return {
        "updated_at": datetime.now(UTC).isoformat(),
        "source": "ESPN",
        "season": season,
        "player": {
            "id": athlete.get("id"),
            "name": athlete.get("displayName"),
            "jersey": athlete.get("jersey"),
            "position": athlete.get("position", {}).get("abbreviation"),
            "position_name": athlete.get("position", {}).get("displayName"),
            "headshot": athlete.get("headshot", {}).get("href"),
            "age": athlete.get("age"),
            "height": athlete.get("displayHeight"),
            "weight": athlete.get("displayWeight"),
            "experience": athlete.get("displayExperience"),
            "college": athlete.get("college", {}).get("name"),
            "status": athlete.get("status", {}).get("name"),
            "draft": athlete.get("displayDraft"),
        },
        "summary": [
            {
                "key": item.get("name"),
                "label": STAT_LABELS.get(item.get("name"), item.get("shortDisplayName") or item.get("displayName")),
                "value": item.get("displayValue"),
            }
            for item in summary.get("statistics", [])
        ],
        "categories": _player_categories(stats, season),
    }


def _stats(data: dict[str, Any]) -> list[dict[str, Any]]:
    wanted = {
        "yardsPerGame": "Yards pro Spiel",
        "netPassingYardsPerGame": "Pass-Yards pro Spiel",
        "rushingYardsPerGame": "Rush-Yards pro Spiel",
        "thirdDownConvPct": "3rd-Down-Quote",
        "turnOverDifferential": "Turnover-Differenz",
        "totalPoints": "Punkte",
    }
    found: dict[str, dict[str, Any]] = {}
    categories = data.get("results", {}).get("stats", {}).get("categories", [])
    for category in categories:
        for stat in category.get("stats", []):
            name = stat.get("name")
            if name in wanted and name not in found:
                value = stat.get("displayValue")
                if name == "thirdDownConvPct" and value is not None:
                    value = f"{value} %"
                found[name] = {"key": name, "label": wanted[name], "value": value}
    return [found[key] for key in wanted if key in found]


def _odds(scoreboard: dict[str, Any], slug: str) -> dict[str, Any] | None:
    now = datetime.now(UTC)
    choices = []
    for event in scoreboard.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        mine, opponent = _competitor(comp, slug)
        odds = (comp.get("odds") or [None])[0]
        if not mine or not opponent or not odds:
            continue
        try:
            date = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if date >= now:
            choices.append((date, event, comp, mine, opponent, odds))
    if not choices:
        return None
    _, event, comp, mine, opponent, odds = min(choices, key=lambda x: x[0])
    money = odds.get("moneyline", {})
    mine_side = "home" if mine.get("homeAway") == "home" else "away"
    opponent_side = "away" if mine_side == "home" else "home"
    return {
        "event_id": event.get("id"),
        "date": event.get("date"),
        "opponent": opponent.get("team", {}).get("displayName"),
        "provider": odds.get("provider", {}).get("name"),
        "details": odds.get("details"),
        "over_under": odds.get("overUnder"),
        "team_moneyline": money.get(mine_side, {}).get("close", {}).get("odds"),
        "opponent_moneyline": money.get(opponent_side, {}).get("close", {}).get("odds"),
        "updated_note": "Quoten können sich jederzeit ändern.",
    }


async def team_detail(slug: str) -> dict[str, Any]:
    slug = slug.lower()
    if not TEAM_RE.fullmatch(slug):
        raise LiveDataError("Ungültiges Team.")
    season = datetime.now(UTC).year
    team_data, schedule, roster, stats, injuries, scoreboard = await asyncio.gather(
        _json(f"/teams/{slug}"),
        _json(f"/teams/{slug}/schedule?season={season}"),
        _json(f"/teams/{slug}/roster"),
        _json(f"/teams/{slug}/statistics"),
        _json("/injuries"),
        _json(f"/scoreboard?dates={season}&limit=1000"),
    )
    raw_team = team_data.get("team", {})
    item = _team(raw_team)
    games = [g for e in schedule.get("events", []) if (g := _game(e, slug))]
    completed = sorted((g for g in games if g["completed"]), key=lambda g: g["date"] or "", reverse=True)[:5]
    upcoming = sorted((g for g in games if not g["completed"]), key=lambda g: g["date"] or "")[:3]
    record = None
    records = raw_team.get("record", {}).get("items", [])
    if records:
        record = records[0].get("summary")
    item.update({"record": record, "standing": raw_team.get("standingSummary")})
    return {
        "updated_at": max(
            x for x in [schedule.get("timestamp"), roster.get("timestamp"), injuries.get("timestamp")] if x
        ),
        "source": "ESPN",
        "team": item,
        "last_games": completed,
        "upcoming_games": upcoming,
        "statistics": _stats(stats),
        "injuries": _injuries(injuries, str(raw_team.get("id"))),
        "roster": _roster(roster),
        "odds": _odds(scoreboard, slug),
    }
