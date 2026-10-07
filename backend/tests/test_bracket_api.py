from datetime import UTC, datetime, timedelta

from app.core.db import get_sessionmaker
from app.services.scheduler import lock_due_matches
from tests.conftest import admin_matches, iso, lock, pick, result, setup_season


def slot_view(bracket: dict, slot: str) -> dict:
    return next(s for s in bracket["slots"] if s["slot"] == slot)


async def test_winner_advances_through_bracket(admin, players):
    env = await setup_season(admin)
    sid, t = env["season"]["id"], env["teams"]
    api = players["florian"]
    for slot, abbr in (("AFC-WC-1", "BUF"), ("AFC-WC-2", "BAL"), ("AFC-WC-3", "MIA")):
        r = await pick(api, sid, slot, t[abbr])
        assert r.status_code == 200, r.text
    bracket = r.json()
    div1, div2 = slot_view(bracket, "AFC-DIV-1"), slot_view(bracket, "AFC-DIV-2")
    # reseeding: seed 1 (KC) hosts the lowest remaining seed (5 MIA), 2 BUF hosts 3 BAL
    assert (div1["home"]["abbreviation"], div1["away"]["abbreviation"]) == ("KC", "MIA")
    assert (div2["home"]["abbreviation"], div2["away"]["abbreviation"]) == ("BUF", "BAL")
    assert div1["teams_source"] == "predicted" and div1["away_origin"] == "AFC-WC-3"

    for slot, abbr in (
        ("AFC-DIV-1", "KC"),
        ("AFC-DIV-2", "BAL"),
        ("AFC-CONF", "BAL"),
        ("NFC-WC-1", "DET"),
        ("NFC-WC-2", "SF"),
        ("NFC-WC-3", "TB"),
        ("NFC-DIV-1", "PHI"),
        ("NFC-DIV-2", "DET"),
        ("NFC-CONF", "DET"),
        ("SB", "DET"),
    ):
        r = await pick(api, sid, slot, t[abbr], 27, 20)
        assert r.status_code == 200, (slot, r.text)
    bracket = r.json()
    sb = slot_view(bracket, "SB")
    assert (sb["home"]["abbreviation"], sb["away"]["abbreviation"]) == ("BAL", "DET")
    assert bracket["champion_team_id"] == t["DET"]
    assert bracket["missing_open_picks"] == 0

    r = await api.post(f"/api/seasons/{sid}/bracket/me/submit")
    assert r.status_code == 200 and r.json()["submitted_at"] is not None


async def test_pick_validation(admin, players):
    env = await setup_season(admin)
    sid, t = env["season"]["id"], env["teams"]
    api = players["florian"]
    assert (await pick(api, sid, "AFC-WC-1", t["KC"])).status_code == 422  # KC not in 2v7
    assert (await pick(api, sid, "AFC-DIV-1", t["KC"])).status_code == 409  # pairing unknown yet
    assert (await pick(api, sid, "AFC-WC-1", t["BUF"], 20, 24)).status_code == 422  # winner must score more
    assert (await pick(api, sid, "AFC-WC-1", t["BUF"], 20, None)).status_code == 422
    assert (await pick(api, sid, "XYZ", t["BUF"])).status_code == 404
    r = await api.post(f"/api/seasons/{sid}/bracket/me/submit")
    assert r.status_code == 422  # bracket incomplete


async def test_changing_pick_cascades_downstream(admin, players):
    env = await setup_season(admin)
    sid, t = env["season"]["id"], env["teams"]
    api = players["florian"]
    for slot, abbr in (
        ("AFC-WC-1", "BUF"),
        ("AFC-WC-2", "BAL"),
        ("AFC-WC-3", "HOU"),
        ("AFC-DIV-1", "HOU"),
        ("AFC-DIV-2", "BUF"),
        ("AFC-CONF", "HOU"),
    ):
        assert (await pick(api, sid, slot, t[abbr])).status_code == 200
    r = await pick(api, sid, "AFC-WC-3", t["MIA"])  # Houston out -> downstream Houston picks removed
    bracket = r.json()
    assert slot_view(bracket, "AFC-DIV-1")["pick"] is None
    assert slot_view(bracket, "AFC-CONF")["pick"] is None
    assert slot_view(bracket, "AFC-DIV-2")["pick"]["winner_team_id"] == t["BUF"]


async def test_tip_lock_blocks_changes(admin, players):
    env = await setup_season(admin)
    sid, t, m = env["season"]["id"], env["teams"], env["matches"]
    api = players["florian"]
    assert (await pick(api, sid, "AFC-WC-1", t["BUF"])).status_code == 200
    await lock(admin, m["AFC-WC-1"]["id"])
    r = await pick(api, sid, "AFC-WC-1", t["PIT"])
    assert r.status_code == 409 and "Änderungsantrag" in r.json()["detail"]
    # admin reopens -> changes possible again
    r = await admin.post(f"/api/admin/matches/{m['AFC-WC-1']['id']}/status", {"action": "reopen"})
    assert r.status_code == 200 and r.json()["status"] == "OPEN"
    assert (await pick(api, sid, "AFC-WC-1", t["PIT"])).status_code == 200


async def test_deadline_locks_automatically(admin, players):
    env = await setup_season(admin)
    sid, t, m = env["season"]["id"], env["teams"], env["matches"]
    api = players["florian"]
    match_id = m["AFC-WC-2"]["id"]
    past = datetime.now(UTC) - timedelta(minutes=1)
    r = await admin.patch(f"/api/admin/matches/{match_id}", {"kickoff_at": iso(past)})
    assert r.json()["locked"] is True  # lock_at reached -> effectively locked immediately
    assert (await pick(api, sid, "AFC-WC-2", t["BAL"])).status_code == 409
    async with get_sessionmaker()() as session:
        assert await lock_due_matches(session) == 1
        await session.commit()
    matches = await admin_matches(admin, sid)
    assert matches["AFC-WC-2"]["status"] == "LOCKED"
    chat = (await api.get("/api/chat/messages")).json()
    assert any(msg["system"] and msg["system"]["type"] == "KICKOFF" for msg in chat)


async def test_picks_hidden_until_lock(admin, players):
    env = await setup_season(admin)
    sid, t, m = env["season"]["id"], env["teams"], env["matches"]
    florian, dennis = players["florian"], players["dennis"]
    await pick(florian, sid, "AFC-WC-1", t["PIT"], 24, 21)
    florian_id = (await florian.get("/api/me")).json()["id"]

    view = (await dennis.get(f"/api/seasons/{sid}/bracket/{florian_id}")).json()
    s = slot_view(view, "AFC-WC-1")
    assert s["has_pick"] is True and s["pick"] is None and s["pick_hidden"] is True
    assert (await dennis.get(f"/api/seasons/{sid}/distribution")).json() == []
    detail = (await dennis.get(f"/api/matches/{m['AFC-WC-1']['id']}")).json()
    assert next(p for p in detail["picks"] if p["user"]["id"] == florian_id)["pick"] is None

    await lock(admin, m["AFC-WC-1"]["id"])
    view = (await dennis.get(f"/api/seasons/{sid}/bracket/{florian_id}")).json()
    assert slot_view(view, "AFC-WC-1")["pick"]["winner_team_id"] == t["PIT"]
    dist = (await dennis.get(f"/api/seasons/{sid}/distribution")).json()
    assert dist[0]["teams"][0] == {"team_id": t["PIT"], "count": 1, "percent": 100}
    # admins always see everything
    view = (await admin.get(f"/api/seasons/{sid}/bracket/{florian_id}")).json()
    assert view["full_visibility"] is True


async def test_compare_highlights_differences(admin, players):
    env = await setup_season(admin)
    sid, t, m = env["season"]["id"], env["teams"], env["matches"]
    florian, dennis = players["florian"], players["dennis"]
    await pick(florian, sid, "AFC-WC-1", t["BUF"])
    await pick(dennis, sid, "AFC-WC-1", t["PIT"])
    await pick(florian, sid, "AFC-WC-2", t["BAL"])
    await pick(dennis, sid, "AFC-WC-2", t["BAL"])
    dennis_id = (await dennis.get("/api/me")).json()["id"]
    r = await florian.get(f"/api/seasons/{sid}/compare", params={"a": "me", "b": dennis_id})
    diff = {d["slot"]: d["state"] for d in r.json()["diff"]}
    assert diff["AFC-WC-1"] == "hidden"  # not locked yet
    await lock(admin, m["AFC-WC-1"]["id"])
    await lock(admin, m["AFC-WC-2"]["id"])
    r = await florian.get(f"/api/seasons/{sid}/compare", params={"a": "me", "b": dennis_id})
    diff = {d["slot"]: d["state"] for d in r.json()["diff"]}
    assert diff["AFC-WC-1"] == "different" and diff["AFC-WC-2"] == "same"


async def test_next_round_created_automatically(admin, players):
    env = await setup_season(admin)
    sid, m = env["season"]["id"], env["matches"]
    for slot, (h, a) in {"AFC-WC-1": (27, 17), "AFC-WC-2": (14, 28), "AFC-WC-3": (24, 20)}.items():
        await lock(admin, m[slot]["id"])
        out = await result(admin, m[slot]["id"], h, a)
    assert {x["slot"] for x in out["advanced"]} == {"AFC-DIV-1", "AFC-DIV-2"}
    matches = await admin_matches(admin, sid)
    # winners BUF(2), LAC(6), HOU(4): KC hosts LAC, BUF hosts HOU
    assert (matches["AFC-DIV-1"]["home_team"]["abbreviation"], matches["AFC-DIV-1"]["away_team"]["abbreviation"]) == (
        "KC",
        "LAC",
    )
    assert (matches["AFC-DIV-2"]["home_team"]["abbreviation"], matches["AFC-DIV-2"]["away_team"]["abbreviation"]) == (
        "BUF",
        "HOU",
    )
    chat = (await players["florian"].get("/api/chat/messages")).json()
    assert any(msg["system"] and msg["system"]["type"] == "NEXT_ROUND" for msg in chat)
    notes = (await players["florian"].get("/api/notifications")).json()
    assert notes["unread"] >= 1


async def test_drag_and_drop_assignment_validation(admin):
    env = await setup_season(admin)
    m, t = env["matches"], env["teams"]
    div = m["AFC-DIV-1"]["id"]
    assert (await admin.patch(f"/api/admin/matches/{div}", {"home_team_id": t["PHI"]})).status_code == 422  # NFC team
    assert (await admin.patch(f"/api/admin/matches/{div}", {"home_team_id": t["NYJ"]})).status_code == 422  # not seeded
    r = await admin.patch(f"/api/admin/matches/{div}", {"home_team_id": t["KC"], "away_team_id": t["PIT"]})
    assert r.status_code == 200 and r.json()["home_team"]["abbreviation"] == "KC"
    # PIT already plays in another divisional match -> refused
    r = await admin.patch(f"/api/admin/matches/{m['AFC-DIV-2']['id']}", {"home_team_id": t["PIT"]})
    assert r.status_code == 422
    sb = m["SB"]["id"]
    assert (
        await admin.patch(f"/api/admin/matches/{sb}", {"home_team_id": t["KC"], "away_team_id": t["BUF"]})
    ).status_code == 422
    assert (
        await admin.patch(f"/api/admin/matches/{sb}", {"home_team_id": t["KC"], "away_team_id": t["PHI"]})
    ).status_code == 200


async def test_wild_card_generation_requires_all_seeds_incl_bye(admin):
    r = await admin.post("/api/admin/seasons", {"name": "2032/2033", "year": 2032})
    sid = r.json()["id"]
    teams = (await admin.get("/api/teams")).json()
    by_abbr = {t["abbreviation"]: t["id"] for t in teams}
    entries = [{"team_id": by_abbr[a], "seed": i + 2} for i, a in enumerate(["BUF", "BAL", "HOU", "MIA", "LAC", "PIT"])]
    assert (await admin.put(f"/api/admin/seasons/{sid}/teams", entries)).status_code == 200
    r = await admin.post(f"/api/admin/seasons/{sid}/generate-wildcard")
    assert r.status_code == 422 and "Seed 1" in r.json()["detail"]
