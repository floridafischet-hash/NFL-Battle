from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models import Team
from app.seed.__main__ import ensure_teams
from app.seed.teams import NFL_TEAMS, OFFICIAL_LOGOS, neutral_logo_url


async def test_every_team_has_its_official_logo(admin):
    teams = {t["abbreviation"]: t for t in (await admin.get("/api/teams")).json()}
    assert len(teams) == 32 == len(OFFICIAL_LOGOS) == len(NFL_TEAMS)
    for abbr, team in teams.items():
        assert team["logo_url"] == OFFICIAL_LOGOS[abbr]
        assert team["logo_url"].startswith("https://a.espncdn.com/i/teamlogos/nfl/")
    # spot checks for the abbreviations that differ on ESPN
    assert teams["WAS"]["logo_url"].endswith("/wsh.png")
    assert teams["LAR"]["logo_url"].endswith("/lar.png")
    assert teams["LV"]["logo_url"].endswith("/lv.png")


async def test_old_installs_get_official_logos_but_custom_ones_stay():
    async with get_sessionmaker()() as session:
        teams = {t.abbreviation: t for t in (await session.execute(select(Team))).scalars()}
        teams["BUF"].logo_url = neutral_logo_url("BUF")
        teams["KC"].logo_url = "/media/logo/ab/custom.webp"
        await session.commit()
        await ensure_teams(session)
        await session.commit()
        teams = {t.abbreviation: t for t in (await session.execute(select(Team))).scalars()}
    assert teams["BUF"].logo_url == OFFICIAL_LOGOS["BUF"]
    assert teams["KC"].logo_url == "/media/logo/ab/custom.webp"
