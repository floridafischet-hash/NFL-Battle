from datetime import UTC, datetime, timedelta

from tests.conftest import Api, admin_matches, iso, lock, pick, setup_season


async def agent_api(admin: Api) -> tuple[Api, dict]:
    r = await admin.post("/api/admin/agent/tokens", {"name": "openclaw"})
    assert r.status_code == 201
    body = r.json()
    assert body["token"].startswith("nbb_")
    return Api(body["token"]), body


def payload(match: dict, home: int, away: int, **extra) -> dict:
    return {
        "match_id": match["id"],
        "home_team": match["home_team"]["abbreviation"],
        "away_team": match["away_team"]["abbreviation"],
        "home_score": home,
        "away_score": away,
        "winner": match["home_team"]["abbreviation"] if home > away else match["away_team"]["abbreviation"],
        "source": "ESPN",
        "source_url": "https://www.espn.com/nfl/game/_/gameId/1",
        "timestamp": iso(datetime.now(UTC)),
        **extra,
    }


async def started_season(admin):
    env = await setup_season(admin, kickoff_in=timedelta(hours=-4))
    return env, await admin_matches(admin, env["season"]["id"])


async def test_agent_permissions(admin, players):
    agent, token = await agent_api(admin)
    assert (await agent.get("/api/agent/whoami")).json()["roles"] == ["AGENT"]
    # agent cannot use user or admin endpoints
    assert (await agent.get("/api/me")).status_code == 403
    assert (await agent.get("/api/admin/users")).status_code == 403
    assert (await agent.get("/api/dashboard")).status_code == 403
    # users and admins cannot use agent endpoints
    assert (await players["florian"].get("/api/agent/matches/pending")).status_code == 403
    assert (await admin.post("/api/agent/results", {})).status_code == 403
    assert (await Api().get("/api/agent/matches")).status_code == 401
    # revoked token is dead
    assert (await admin.delete(f"/api/admin/agent/tokens/{token['id']}")).status_code == 204
    assert (await agent.get("/api/agent/whoami")).status_code == 401
    assert (await Api("nbb_invalid").get("/api/agent/whoami")).status_code == 401


async def test_agent_result_applied_end_to_end(admin, players):
    _, matches = await started_season(admin)
    agent, _ = await agent_api(admin)
    pending = (await agent.get("/api/agent/matches/pending")).json()
    assert {p["slot"] for p in pending} >= {"AFC-WC-1", "NFC-WC-3"}

    m = matches["AFC-WC-1"]
    r = await agent.post("/api/agent/results", payload(m, 31, 24))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPLIED"
    detail = (await players["florian"].get(f"/api/matches/{m['id']}")).json()["match"]
    assert detail["status"] == "FINAL" and detail["result_source"] == "AGENT"
    assert (detail["home_score"], detail["away_score"]) == (31, 24)
    # same report again -> duplicate, nothing changes
    r = await agent.post("/api/agent/results", payload(m, 31, 24))
    assert r.status_code == 200 and r.json()["status"] == "DUPLICATE"
    # different score for an already final match -> review
    r = await agent.post("/api/agent/results", payload(m, 30, 24))
    assert r.status_code == 202 and r.json()["status"] == "REVIEW_REQUIRED"
    overview = (await admin.get("/api/admin/agent/overview")).json()
    assert overview["last_run"]["status"] == "REVIEW_REQUIRED"
    assert any(rep["status"] == "APPLIED" and rep["source"] == "ESPN" for rep in overview["reports"])
    audit = (await admin.get("/api/admin/audit", params={"actor_type": "AGENT"})).json()["items"]
    assert any(a["action"] == "MATCH_RESULT_SET" and a["source"] == "AGENT" for a in audit)
    admin_notes = (await admin.get("/api/notifications")).json()["items"]
    assert any(n["type"] == "REVIEW_REQUIRED" for n in admin_notes)


async def test_agent_validation(admin):
    env, matches = await started_season(admin)
    agent, _ = await agent_api(admin)
    m = matches["AFC-WC-2"]
    cases = [
        ({**payload(m, 28, 14), "match_id": 99999}, 404),
        ({**payload(m, 28, 14), "home_team": "NE"}, 422),  # wrong teams
        (payload(m, 21, 21), 422),  # tie
        ({**payload(m, 28, 14), "winner": m["away_team"]["abbreviation"]}, 422),  # winner inconsistent
        ({**payload(m, 28, 14), "timestamp": iso(datetime.now(UTC) + timedelta(days=1))}, 422),
        ({"match_id": m["id"], "home_score": "x"}, 422),  # malformed
    ]
    for body, code in cases:
        r = await agent.post("/api/agent/results", body)
        assert r.status_code == code, (body, r.text)
        assert r.json()["status"] == "REJECTED"
    overview = (await admin.get("/api/admin/agent/overview")).json()
    assert len(overview["errors"]) == len(cases)
    # swapped home/away is detected and corrected
    swapped = {
        **payload(m, 14, 28),
        "home_team": m["away_team"]["abbreviation"],
        "away_team": m["home_team"]["abbreviation"],
        "winner": m["home_team"]["abbreviation"],
    }
    r = await agent.post("/api/agent/results", swapped)
    assert r.status_code == 200 and r.json()["status"] == "APPLIED" and "vertauscht" in r.json()["message"]
    final = (await admin_matches(admin, env["season"]["id"]))["AFC-WC-2"]
    assert (final["home_score"], final["away_score"]) == (28, 14)


async def test_game_not_started_is_rejected(admin):
    env = await setup_season(admin, kickoff_in=timedelta(hours=5))
    agent, _ = await agent_api(admin)
    m = env["matches"]["AFC-WC-1"]
    r = await agent.post("/api/agent/results", payload(m, 31, 24))
    assert r.status_code == 409 and r.json()["status"] == "REJECTED"


async def test_untrusted_or_conflicting_sources_need_review(admin, players):
    env, matches = await started_season(admin)
    agent, _ = await agent_api(admin)
    m1, m2, m3 = matches["NFC-WC-1"], matches["NFC-WC-2"], matches["NFC-WC-3"]
    r = await agent.post(
        "/api/agent/results", payload(m1, 31, 23, source="Blog", source_url="https://random-blog.example/x")
    )
    assert r.status_code == 202 and r.json()["status"] == "REVIEW_REQUIRED"
    conflict = payload(
        m2,
        20,
        23,
        sources=[
            {"source": "NFL.com", "source_url": "https://www.nfl.com/games/x", "home_score": 20, "away_score": 24}
        ],
    )
    r = await agent.post("/api/agent/results", conflict)
    assert r.status_code == 202 and "Widersprüchliche" in r.json()["message"]
    agree = payload(
        m3,
        17,
        24,
        sources=[
            {"source": "NFL.com", "source_url": "https://www.nfl.com/games/y", "home_score": 17, "away_score": 24}
        ],
    )
    assert (await agent.post("/api/agent/results", agree)).json()["status"] == "APPLIED"
    status = {s: m["status"] for s, m in (await admin_matches(admin, env["season"]["id"])).items()}
    assert status["NFC-WC-1"] != "FINAL" and status["NFC-WC-2"] != "FINAL" and status["NFC-WC-3"] == "FINAL"

    # admin resolves the review by accepting the report
    reports = (await admin.get("/api/admin/agent/overview")).json()["reports"]
    review = next(rep for rep in reports if rep["match"]["slot"] == "NFC-WC-1" and rep["status"] == "REVIEW_REQUIRED")
    r = await admin.post(f"/api/admin/agent/reports/{review['id']}/accept")
    assert r.status_code == 200 and r.json()["status"] == "APPLIED"
    assert (await admin_matches(admin, env["season"]["id"]))["NFC-WC-1"]["status"] == "FINAL"
    other = next(rep for rep in reports if rep["match"]["slot"] == "NFC-WC-2")
    assert (await admin.post(f"/api/admin/agent/reports/{other['id']}/reject")).json()["status"] == "REJECTED"


async def test_min_confirmations(admin, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "agent_min_confirmations", 2)
    env, matches = await started_season(admin)
    agent, _ = await agent_api(admin)
    m = matches["AFC-WC-3"]
    r = await agent.post("/api/agent/results", payload(m, 24, 20))
    assert r.status_code == 202 and r.json()["status"] == "PENDING_CONFIRMATION"
    r = await agent.post("/api/agent/results", payload(m, 24, 20, source="NFL", source_url="https://www.nfl.com/g/3"))
    assert r.status_code == 200 and r.json()["status"] == "APPLIED"


async def test_agent_flow_scores_and_bot_message(admin, players):
    env = await setup_season(admin, kickoff_in=timedelta(hours=2))
    sid, t = env["season"]["id"], env["teams"]
    await pick(players["florian"], sid, "AFC-WC-1", t["BUF"], 31, 24)
    await pick(players["dennis"], sid, "AFC-WC-1", t["PIT"], 24, 10)
    m = env["matches"]["AFC-WC-1"]
    past = datetime.now(UTC) - timedelta(hours=4)
    await admin.patch(f"/api/admin/matches/{m['id']}", {"kickoff_at": iso(past)})
    await lock(admin, m["id"])
    agent, _ = await agent_api(admin)
    r = await agent.post("/api/agent/results", payload(m, 31, 24))
    assert r.json()["status"] == "APPLIED"
    lb = {
        row["user"]["display_name"]: row
        for row in (await players["florian"].get(f"/api/seasons/{sid}/leaderboard")).json()
    }
    assert lb["Florian"]["points"] == 3 and lb["Dennis"]["points"] == 0
    chat = (await players["dennis"].get("/api/chat/messages")).json()
    final = [c for c in chat if c["system"] and c["system"]["type"] == "FINAL"][-1]
    assert "Florian 🎯 +3" in final["body"] and "Neue Rangliste" in final["body"]


async def test_schedule_and_halftime_events(admin):
    env = await setup_season(admin, kickoff_in=timedelta(days=2))
    agent, _ = await agent_api(admin)
    m = env["matches"]["AFC-WC-1"]
    new_kickoff = datetime.now(UTC) + timedelta(days=3)
    r = await agent.post(
        "/api/agent/schedule",
        {
            "match_id": m["id"],
            "kickoff_at": iso(new_kickoff),
            "venue": "Highmark Stadium",
            "source": "NFL",
            "source_url": "https://www.nfl.com/schedules",
        },
    )
    assert r.status_code == 200
    updated = (await admin_matches(admin, env["season"]["id"]))["AFC-WC-1"]
    assert updated["venue"] == "Highmark Stadium" and updated["lock_at"] is not None
    r = await agent.post(
        "/api/agent/events",
        {"match_id": m["id"], "type": "HALFTIME", "home_score": 14, "away_score": 10, "source": "ESPN"},
    )
    assert r.status_code == 200 and r.json()["status"] == "OK"
    r = await agent.post(
        "/api/agent/events",
        {"match_id": m["id"], "type": "HALFTIME", "home_score": 14, "away_score": 10, "source": "ESPN"},
    )
    assert r.json()["status"] == "DUPLICATE"


async def test_admin_result_check_request(admin):
    env, matches = await started_season(admin)
    agent, _ = await agent_api(admin)
    r = await admin.post("/api/admin/agent/check", {"match_ids": [matches["SB"]["id"]]})
    assert r.status_code == 200 and r.json()["matches"] == 1
    pending = (await agent.get("/api/agent/matches/pending")).json()
    assert any(p["slot"] == "SB" and p["result_check_requested"] for p in pending)
