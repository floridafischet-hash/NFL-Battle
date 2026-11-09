import pytest

from app.services import nfl_live

pytestmark = pytest.mark.asyncio


async def test_each_user_has_independent_team_favorites(players, monkeypatch):
    async def fake_teams():
        return {"updated_at": None, "source": "test", "teams": []}

    monkeypatch.setattr(nfl_live, "teams", fake_teams)
    florian = players["florian"]
    dennis = players["dennis"]

    response = await florian.put("/api/live/teams/favorites", {"favorites": ["kc", "buf"]})
    assert response.status_code == 200, response.text
    response = await dennis.put("/api/live/teams/favorites", {"favorites": ["det"]})
    assert response.status_code == 200, response.text

    assert (await florian.get("/api/live/teams")).json()["favorites"] == ["kc", "buf"]
    assert (await dennis.get("/api/live/teams")).json()["favorites"] == ["det"]


async def test_regular_user_can_change_own_favorites(players):
    response = await players["stefan"].put("/api/live/teams/favorites", {"favorites": ["gb"]})
    assert response.status_code == 200, response.text
    assert response.json() == {"favorites": ["gb"]}


async def test_games_include_personal_favorites_and_conference_rank(players, monkeypatch):
    async def fake_games():
        return {"regular_season": True, "games": []}

    async def fake_standings():
        return [
            {"slug": "buf", "conference": "AFC", "rank": 1},
            {"slug": "kc", "conference": "AFC", "rank": 4},
        ]

    monkeypatch.setattr(nfl_live, "regular_season_games", fake_games)
    monkeypatch.setattr(nfl_live, "conference_standings", fake_standings)
    client = players["florian"]
    await client.put("/api/live/teams/favorites", {"favorites": ["kc", "buf"]})

    response = await client.get("/api/live/games")

    assert response.status_code == 200, response.text
    assert response.json()["favorites"] == ["kc", "buf"]
    assert response.json()["favorite_standings"] == [
        {"slug": "kc", "conference": "AFC", "rank": 4},
        {"slug": "buf", "conference": "AFC", "rank": 1},
    ]


async def test_division_standings_include_records_and_statistics(monkeypatch):
    async def fake_fetch_json(url, cache_seconds=nfl_live.CACHE_SECONDS):
        return {
            "children": [
                {
                    "abbreviation": "AFC",
                    "children": [
                        {
                            "name": "AFC North",
                            "abbreviation": "NORTH",
                            "standings": {
                                "entries": [
                                    {
                                        "team": {
                                            "abbreviation": "BAL",
                                            "displayName": "Baltimore Ravens",
                                            "shortDisplayName": "Ravens",
                                            "logos": [{"href": "logo.svg"}],
                                        },
                                        "stats": [
                                            {"name": "wins", "displayValue": "7"},
                                            {"name": "losses", "displayValue": "2"},
                                            {"name": "divisionRecord", "displayValue": "3-0"},
                                            {"name": "vs. Conf.", "displayValue": "5-1"},
                                            {"name": "pointDifferential", "displayValue": "+42"},
                                            {"name": "streak", "displayValue": "W4"},
                                        ],
                                    }
                                ]
                            },
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(nfl_live, "_fetch_json", fake_fetch_json)

    divisions = await nfl_live.division_standings()

    assert divisions == [
        {
            "name": "AFC North",
            "abbreviation": "NORTH",
            "conference": "AFC",
            "teams": [
                {
                    "rank": 1,
                    "slug": "bal",
                    "name": "Baltimore Ravens",
                    "short_name": "Ravens",
                    "abbreviation": "BAL",
                    "logo": "logo.svg",
                    "wins": "7",
                    "losses": "2",
                    "ties": None,
                    "win_percent": None,
                    "home": None,
                    "road": None,
                    "division": "3-0",
                    "conference": "5-1",
                    "points_for": None,
                    "points_against": None,
                    "differential": "+42",
                    "streak": "W4",
                }
            ],
        }
    ]
