from sqlalchemy import func, select

from app.core.db import get_sessionmaker
from app.models import Score
from tests.conftest import admin_matches, lock, pick, result, setup_season


async def leaderboard(api, sid) -> dict[str, dict]:
    rows = (await api.get(f"/api/seasons/{sid}/leaderboard")).json()
    return {r["user"]["display_name"]: r for r in rows}


async def score_rows(match_id: int) -> int:
    async with get_sessionmaker()() as session:
        return (await session.execute(select(func.count(Score.id)).where(Score.match_id == match_id))).scalar_one()


async def test_winner_and_exact_score_points(admin, players):
    env = await setup_season(admin)
    sid, t, m = env["season"]["id"], env["teams"], env["matches"]
    await pick(players["florian"], sid, "AFC-WC-1", t["BUF"], 27, 20)  # winner only
    await pick(players["dennis"], sid, "AFC-WC-1", t["BUF"], 31, 24)  # exact
    await pick(players["stefan"], sid, "AFC-WC-1", t["PIT"], 31, 24)  # wrong winner
    mid = m["AFC-WC-1"]["id"]
    await lock(admin, mid)
    out = await result(admin, mid, 31, 24)
    points = {p["display_name"]: p for p in out["points"]}
    assert points["Florian"]["points"] == 1 and points["Florian"]["icon"] == "✅"
    assert points["Dennis"]["points"] == 3 and points["Dennis"]["icon"] == "🎯"
    assert points["Stefan"]["points"] == 0 and points["Stefan"]["icon"] == "❌"
    lb = await leaderboard(players["florian"], sid)
    assert lb["Dennis"]["rank"] == 1 and lb["Dennis"]["exact_scores"] == 1
    assert lb["Florian"]["rank"] == 2 and lb["Florian"]["correct_winners"] == 1
    assert lb["Stefan"]["wrong_picks"] == 1 and lb["Florian"]["is_me"] is True

    chat = (await players["stefan"].get("/api/chat/messages")).json()
    final = [c for c in chat if c["system"] and c["system"]["type"] == "FINAL"][-1]
    assert "Bills 31 : 24 Steelers" in final["body"] and "Dennis 🎯 +3" in final["body"]
    assert final["user"]["is_bot"] is True and final["user"]["display_name"] == "NFL Bot"


async def test_result_correction_recalculates_without_double_points(admin, players):
    env = await setup_season(admin)
    sid, t, m = env["season"]["id"], env["teams"], env["matches"]
    await pick(players["florian"], sid, "AFC-WC-1", t["BUF"], 31, 24)
    await pick(players["dennis"], sid, "AFC-WC-1", t["PIT"], 21, 20)
    mid = m["AFC-WC-1"]["id"]
    await lock(admin, mid)
    await result(admin, mid, 31, 24)
    assert (await leaderboard(admin, sid))["Florian"]["points"] == 3
    # same result again -> idempotent
    await result(admin, mid, 31, 24)
    assert await score_rows(mid) == 2  # one row per bracket (florian, dennis); no duplicates
    # correction: Steelers actually won
    out = await result(admin, mid, 20, 21)
    assert out["correction"] is True
    lb = await leaderboard(admin, sid)
    assert lb["Florian"]["points"] == 0 and lb["Dennis"]["points"] == 3
    assert await score_rows(mid) == 2
    audit = (await admin.get("/api/admin/audit", params={"action": "MATCH_RESULT_CORRECTED"})).json()["items"]
    assert audit and audit[0]["old_value"]["home_score"] == 31 and audit[0]["new_value"]["home_score"] == 20


async def test_correction_blocked_when_next_round_started(admin, players):
    env = await setup_season(admin)
    m = env["matches"]
    for slot, (h, a) in {"AFC-WC-1": (27, 17), "AFC-WC-2": (28, 14), "AFC-WC-3": (24, 20)}.items():
        await lock(admin, m[slot]["id"])
        await result(admin, m[slot]["id"], h, a)
    matches = await admin_matches(admin, env["season"]["id"])
    await lock(admin, matches["AFC-DIV-2"]["id"])
    r = await admin.post(f"/api/admin/matches/{m['AFC-WC-1']['id']}/result", {"home_score": 10, "away_score": 17})
    assert r.status_code == 409


async def test_reset_result_and_recalculate_with_new_config(admin, players):
    env = await setup_season(admin)
    sid, t, m = env["season"]["id"], env["teams"], env["matches"]
    await pick(players["florian"], sid, "AFC-WC-1", t["BUF"], 31, 24)
    mid = m["AFC-WC-1"]["id"]
    await lock(admin, mid)
    await result(admin, mid, 31, 24)
    assert (await leaderboard(admin, sid))["Florian"]["points"] == 3
    r = await admin.patch(f"/api/admin/seasons/{sid}", {"exact_score_points": 5, "winner_points": 2})
    assert r.status_code == 200
    r = await admin.post(f"/api/admin/seasons/{sid}/recalculate")
    assert r.status_code == 200 and r.json()["total_points_after"] == 5
    assert (await leaderboard(admin, sid))["Florian"]["points"] == 5
    r = await admin.post(f"/api/admin/matches/{mid}/reset-result")
    assert r.status_code == 200 and r.json()["status"] == "LOCKED"
    assert (await leaderboard(admin, sid))["Florian"]["points"] == 0
    assert await score_rows(mid) == 0


async def test_void_match_awards_no_points(admin, players):
    env = await setup_season(admin)
    sid, t, m = env["season"]["id"], env["teams"], env["matches"]
    await pick(players["florian"], sid, "AFC-WC-1", t["BUF"])
    mid = m["AFC-WC-1"]["id"]
    r = await admin.post(f"/api/admin/matches/{mid}/status", {"action": "void"})
    assert r.status_code == 200 and r.json()["status"] == "VOID"
    r = await admin.post(f"/api/admin/matches/{mid}/result", {"home_score": 20, "away_score": 10})
    assert r.status_code == 409


async def test_change_request_flow(admin, players):
    env = await setup_season(admin)
    sid, t, m = env["season"]["id"], env["teams"], env["matches"]
    florian = players["florian"]
    mid = m["AFC-WC-2"]["id"]
    await pick(florian, sid, "AFC-WC-2", t["BAL"], 24, 17)
    body = {"winner_team_id": t["LAC"], "winner_score": 21, "loser_score": 20, "reason": "Verklickt"}
    r = await florian.post(f"/api/matches/{mid}/change-requests", body)
    assert r.status_code == 409  # still open -> change directly
    await lock(admin, mid)
    r = await florian.post(f"/api/matches/{mid}/change-requests", body)
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["old"]["winner_team_id"] == t["BAL"] and req["new"]["winner_team_id"] == t["LAC"]
    assert (await florian.post(f"/api/matches/{mid}/change-requests", body)).status_code == 409  # one pending max
    assert (await florian.post(f"/api/admin/change-requests/{req['id']}/approve", {})).status_code == 403

    pending = (await admin.get("/api/admin/change-requests", params={"status": "PENDING"})).json()
    assert [p["id"] for p in pending] == [req["id"]]
    assert pending[0]["user"]["display_name"] == "Florian" and pending[0]["created_at"]
    r = await admin.post(f"/api/admin/change-requests/{req['id']}/approve", {"note": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    bracket = (await florian.get(f"/api/seasons/{sid}/bracket/me")).json()
    slot = next(s for s in bracket["slots"] if s["slot"] == "AFC-WC-2")
    assert slot["pick"] == {"winner_team_id": t["LAC"], "winner_score": 21, "loser_score": 20}
    assert (await admin.post(f"/api/admin/change-requests/{req['id']}/reject", {})).status_code == 409

    # second request gets rejected
    body2 = {"winner_team_id": t["BAL"], "winner_score": None, "loser_score": None}
    req2 = (await florian.post(f"/api/matches/{mid}/change-requests", body2)).json()
    r = await admin.post(f"/api/admin/change-requests/{req2['id']}/reject", {"note": "zu spät"})
    assert r.json()["status"] == "REJECTED" and r.json()["decision_note"] == "zu spät"
    actions = {a["action"] for a in (await admin.get("/api/admin/audit")).json()["items"]}
    assert {"CHANGE_REQUEST_CREATED", "CHANGE_REQUEST_APPROVED", "CHANGE_REQUEST_REJECTED"} <= actions
    notes = (await florian.get("/api/notifications")).json()["items"]
    assert any(n["type"] == "CHANGE_REQUEST_APPROVED" for n in notes)


async def test_super_bowl_bonus_completes_season_and_hall_of_fame(admin, players):
    env = await setup_season(admin, champion_bonus=5)
    sid, t = env["season"]["id"], env["teams"]
    florian, dennis = players["florian"], players["dennis"]
    path = {
        "AFC-WC-1": "BUF",
        "AFC-WC-2": "BAL",
        "AFC-WC-3": "HOU",
        "NFC-WC-1": "DET",
        "NFC-WC-2": "SF",
        "NFC-WC-3": "TB",
        "AFC-DIV-1": "KC",
        "AFC-DIV-2": "BUF",
        "NFC-DIV-1": "PHI",
        "NFC-DIV-2": "DET",
        "AFC-CONF": "KC",
        "NFC-CONF": "DET",
        "SB": "DET",
    }
    for slot, abbr in path.items():
        assert (await pick(florian, sid, slot, t[abbr])).status_code == 200
        alt = "KC" if slot == "SB" else abbr
        assert (await pick(dennis, sid, slot, t[alt])).status_code == 200

    scores = {
        "AFC-WC-1": (27, 17),
        "AFC-WC-2": (28, 14),
        "AFC-WC-3": (24, 20),
        "NFC-WC-1": (31, 23),
        "NFC-WC-2": (30, 20),
        "NFC-WC-3": (24, 17),
        "AFC-DIV-1": (30, 21),
        "AFC-DIV-2": (27, 24),
        "NFC-DIV-1": (28, 20),
        "NFC-DIV-2": (35, 24),
        "AFC-CONF": (24, 20),
        "NFC-CONF": (17, 27),
        "SB": (20, 31),
    }
    for slot, (h, a) in scores.items():
        matches = await admin_matches(admin, sid)
        assert matches[slot]["home_team"] is not None, slot
        await lock(admin, matches[slot]["id"])
        out = await result(admin, matches[slot]["id"], h, a)
    assert out["season_completed"] is True
    lb = await leaderboard(admin, sid)
    # 13 correct winners for Florian (+5 champion bonus), Dennis 12 correct and no bonus
    assert lb["Florian"]["points"] == 13 + 5 and lb["Florian"]["champion_correct"] is True
    assert lb["Dennis"]["points"] == 12 and lb["Florian"]["rank"] == 1

    season = (await florian.get("/api/seasons")).json()[0]
    assert season["status"] == "COMPLETED" and season["champion_team"]["abbreviation"] == "DET"
    hof = (await florian.get("/api/hall-of-fame")).json()
    assert hof["seasons"][0]["winner_display_name"] == "Florian"
    assert hof["seasons"][0]["winner_sb_pick_team"]["abbreviation"] == "DET"
    assert hof["all_time"][0]["user"]["display_name"] == "Florian" and hof["all_time"][0]["titles"] == 1
    chat = (await florian.get("/api/chat/messages")).json()
    assert any(c["system"] and c["system"]["type"] == "CHAMPION" for c in chat)
    assert (await pick(florian, sid, "SB", t["KC"])).status_code == 409  # completed season is read-only

    stats = (await florian.get("/api/stats/users/me", params={"season_id": sid})).json()
    assert stats["season"]["correct_winners"] == 13 and stats["season"]["best_streak"] == 13
    assert stats["season"]["hit_rate"] == 100.0 and stats["totals"]["titles"] == 1
    cmp = (
        await florian.get(
            "/api/stats/compare", params={"a": "me", "b": (await dennis.get("/api/me")).json()["id"], "season_id": sid}
        )
    ).json()
    assert cmp["head_to_head"]["a_better"] == 1 and cmp["same_picks"] == 12
