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
