"""ChatGPT result agent: OpenAI is replaced by an httpx mock transport; everything else is real."""

import json
import re
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.services import result_agent
from app.services.agent import process_result
from tests.conftest import Api, admin_matches, iso, lock, pick, setup_season

KEY = "sk-test-SECRETKEY-1234567890"
ESPN = "https://www.espn.com/nfl/game/_/gameId/{}"
NFL = "https://www.nfl.com/games/{}"


@pytest.fixture
def openai(monkeypatch):
    """Configured agent + a fake OpenAI. ``fake.answers[home_abbr]`` controls the answer per game."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", SecretStr(KEY))
    monkeypatch.setattr(settings, "openai_api_key_file", None)
    monkeypatch.setattr(settings, "result_agent_enabled", True)

    class Fake:
        def __init__(self):
            self.answers: dict[str, dict] = {}
            self.requests: list[dict] = []
            self.status = 200
            self.grounded = True

        def handler(self, request: httpx.Request) -> httpx.Response:
            assert request.headers["authorization"] == f"Bearer {KEY}"
            if request.method == "GET":
                return httpx.Response(self.status, json={"id": "gpt-5.4-mini", "object": "model"})
            body = json.loads(request.content)
            self.requests.append(body)
            if self.status != 200:
                return httpx.Response(
                    self.status, json={"error": {"message": f"Incorrect API key provided: {KEY[:8]}***7890"}}
                )
            home = re.search(r"Home team: .* \((\w+)\)", body["input"]).group(1)
            away = re.search(r"Away team: .* \((\w+)\)", body["input"]).group(1)
            pending = {"status": "NOT_FINISHED", "home_score": None, "away_score": None, "sources": []}
            answer = {
                "home_team": home,
                "away_team": away,
                "winner": None,
                "note": "",
                **self.answers.get(home, pending),
            }
            urls = [s["url"] for s in answer.get("sources", [])]
            output = [
                {
                    "type": "web_search_call",
                    "id": "ws_1",
                    "status": "completed",
                    "action": {
                        "type": "search",
                        "query": "score",
                        "sources": [{"type": "url", "url": u} for u in urls] if self.grounded else [],
                    },
                },
                {
                    "type": "message",
                    "id": "msg_1",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": json.dumps(answer), "annotations": []}],
                },
            ]
            return httpx.Response(
                200,
                json={"status": "completed", "output": output, "usage": {"input_tokens": 900, "output_tokens": 120}},
            )

        def client(self) -> httpx.AsyncClient:
            return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    return Fake()


def final(home: int, away: int, *, sources: list[tuple[str, str]] | None = None, mid: int = 1) -> dict:
    sources = sources if sources is not None else [("ESPN", ESPN.format(mid)), ("NFL.com", NFL.format(mid))]
    return {
        "status": "FINAL",
        "home_score": home,
        "away_score": away,
        "sources": [{"name": n, "url": u, "home_score": home, "away_score": away} for n, u in sources],
    }


async def run(fake) -> list[dict]:
    async with fake.client() as client:
        return await result_agent.run_once(client)


async def started_season(admin):
    env = await setup_season(admin, kickoff_in=timedelta(hours=-4))
    return env, await admin_matches(admin, env["season"]["id"])


# ------------------------------------------------------------------ access


async def test_external_agent_api_is_gone(admin, players):
    assert (await admin.post("/api/agent/results", {})).status_code == 404
    assert (await Api().get("/api/agent/matches/pending")).status_code == 404
    assert (await admin.post("/api/admin/agent/tokens", {"name": "x"})).status_code in (404, 405)
    # old style tokens are not accepted anywhere
    assert (await Api("nbb_" + "x" * 40).get("/api/me")).status_code == 401
    # only admins see the agent overview, and it never contains the key
    assert (await players["florian"].get("/api/admin/agent/overview")).status_code == 403


async def test_overview_never_exposes_the_key(admin, openai):
    r = await admin.get("/api/admin/agent/overview")
    assert r.status_code == 200
    assert KEY not in r.text
    config = r.json()["config"]
    assert config["configured"] and config["has_key"] and config["min_confirmations"] == 2


async def test_not_configured_does_nothing(admin):
    await started_season(admin)
    assert not result_agent.is_configured()
    assert await result_agent.run_once(httpx.AsyncClient(transport=httpx.MockTransport(lambda r: 1 / 0))) == []


async def test_connection_test(admin, openai, monkeypatch):
    async with openai.client() as client:
        assert (await result_agent.test_connection(client))["ok"] is True
        openai.status = 401
        r = await result_agent.test_connection(client)
    assert r["ok"] is False and "401" in r["message"] and KEY not in r["message"]
    # the admin endpoint is wired up (no key in the response either)
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
    r = await admin.post("/api/admin/agent/test")
    assert r.status_code == 200 and r.json()["ok"] is False


# ------------------------------------------------------------------ research flow


async def test_chatgpt_result_is_applied(admin, players, openai):
    env, matches = await started_season(admin)
    sid = env["season"]["id"]
    for m in matches.values():
        if m["home_team"]:
            openai.answers[m["home_team"]["abbreviation"]] = final(31, 24, mid=m["id"])
    results = await run(openai)
    assert len(results) == get_settings().result_agent_max_matches_per_run == 3
    assert all(r["status"] == "APPLIED" for r in results), results
    # the request is restricted to trusted sites, structured and not stored at OpenAI
    request = openai.requests[0]
    assert request["tools"][0]["filters"]["allowed_domains"] == get_settings().trusted_domains
    assert request["text"]["format"]["strict"] is True and request["store"] is False
    assert "web_search_call.action.sources" in request["include"]

    after = await admin_matches(admin, sid)
    applied = [s for s, m in after.items() if m["status"] == "FINAL"]
    assert len(applied) == 3 and all(after[s]["result_source"] == "AGENT" for s in applied)
    overview = (await admin.get("/api/admin/agent/overview")).json()
    assert overview["config"]["calls_last_24h"] == 3
    research_runs = [r for r in overview["runs"] if r["kind"] == "RESEARCH"]
    assert research_runs and research_runs[0]["request_payload"]["usage"]["input_tokens"] == 900
    assert any(rep["status"] == "APPLIED" and rep["source"] == "ESPN" for rep in overview["reports"])
    audit = (await admin.get("/api/admin/audit", params={"actor_type": "AGENT"})).json()["items"]
    assert any(a["action"] == "MATCH_RESULT_SET" for a in audit)
    assert any(a["actor_label"].startswith("ChatGPT") for a in audit)

    # next tick handles the remaining three games, then nothing is due anymore
    assert len(await run(openai)) == 3
    assert await run(openai) == []
    assert len(openai.requests) == 6


async def test_invented_links_go_to_review(admin, openai):
    env, matches = await started_season(admin)
    m = matches["AFC-WC-1"]
    openai.grounded = False  # the search did not visit the URLs the model reports
    for mm in matches.values():
        if mm["home_team"]:
            openai.answers[mm["home_team"]["abbreviation"]] = final(27, 17, mid=mm["id"])
    await admin.post("/api/admin/agent/check", {"match_ids": [m["id"]]})
    results = await run(openai)
    assert results[0]["match_id"] == m["id"] and results[0]["status"] == "REVIEW_REQUIRED"
    overview = (await admin.get("/api/admin/agent/overview")).json()
    review = next(
        r for r in overview["reports"] if r["status"] == "REVIEW_REQUIRED" and r["match"]["slot"] == "AFC-WC-1"
    )
    assert "Websuche" in review["review_reason"]
    assert (await admin_matches(admin, env["season"]["id"]))["AFC-WC-1"]["status"] != "FINAL"
    notes = (await admin.get("/api/notifications")).json()["items"]
    assert any(n["type"] == "REVIEW_REQUIRED" for n in notes)
    # admin accepts after checking the sources
    r = await admin.post(f"/api/admin/agent/reports/{review['id']}/accept")
    assert r.status_code == 200 and r.json()["status"] == "APPLIED"
    assert (await admin_matches(admin, env["season"]["id"]))["AFC-WC-1"]["status"] == "FINAL"


async def test_untrusted_and_conflicting_sources(admin, openai):
    _, matches = await started_season(admin)
    a, b = matches["NFC-WC-1"], matches["NFC-WC-2"]
    openai.answers[a["home_team"]["abbreviation"]] = final(31, 23, sources=[("Blog", "https://random-blog.example/x")])
    conflict = final(20, 23, mid=b["id"])
    conflict["sources"][1]["away_score"] = 24
    openai.answers[b["home_team"]["abbreviation"]] = conflict
    await admin.post("/api/admin/agent/check", {"match_ids": [a["id"], b["id"]]})
    results = {r["match_id"]: r for r in await run(openai)}
    assert results[a["id"]]["status"] == "REVIEW_REQUIRED"
    assert results[b["id"]]["status"] == "REVIEW_REQUIRED" and "Widersprüchliche" in results[b["id"]]["message"]


async def test_one_source_waits_for_confirmation(admin, openai):
    _, matches = await started_season(admin)
    m = matches["AFC-WC-3"]
    openai.answers[m["home_team"]["abbreviation"]] = final(24, 20, sources=[("ESPN", ESPN.format(3))])
    await admin.post("/api/admin/agent/check", {"match_ids": [m["id"]]})
    assert (await run(openai))[0]["status"] == "PENDING_CONFIRMATION"
    # a later research with a second site confirms it
    openai.answers[m["home_team"]["abbreviation"]] = final(24, 20, sources=[("NFL.com", NFL.format(3))])
    await admin.post("/api/admin/agent/check", {"match_ids": [m["id"]]})
    assert (await run(openai))[0]["status"] == "APPLIED"


async def test_not_finished_is_retried_later(admin, openai, monkeypatch):
    _, matches = await started_season(admin)
    for m in matches.values():
        if m["home_team"]:
            openai.answers[m["home_team"]["abbreviation"]] = {
                "status": "NOT_FINISHED",
                "home_score": None,
                "away_score": None,
                "sources": [],
            }
    monkeypatch.setattr(get_settings(), "result_agent_max_matches_per_run", 6)
    results = await run(openai)
    assert len(results) == 6 and {r["status"] for r in results} == {"NO_RESULT"}
    assert await run(openai) == []  # retry only after RESULT_AGENT_RETRY_MINUTES
    monkeypatch.setattr(get_settings(), "result_agent_retry_minutes", 0)
    assert len(await run(openai)) == 6


async def test_first_check_waits_for_the_game_to_end(admin, openai):
    env = await setup_season(admin, kickoff_in=timedelta(minutes=-30))
    for m in env["matches"].values():
        if m["home_team"]:
            openai.answers[m["home_team"]["abbreviation"]] = final(10, 3, mid=m["id"])
    assert await run(openai) == []  # kickoff 30 min ago: too early (RESULT_AGENT_FIRST_CHECK_MINUTES)
    assert openai.requests == []


async def test_daily_limit(admin, openai, monkeypatch):
    _, matches = await started_season(admin)
    for m in matches.values():
        if m["home_team"]:
            openai.answers[m["home_team"]["abbreviation"]] = {
                "status": "NOT_FOUND",
                "home_score": None,
                "away_score": None,
                "sources": [],
            }
    monkeypatch.setattr(get_settings(), "result_agent_max_calls_per_day", 2)
    assert len(await run(openai)) == 2
    monkeypatch.setattr(get_settings(), "result_agent_retry_minutes", 0)
    assert await run(openai) == []
    assert len(openai.requests) == 2


async def test_openai_errors_are_recorded_without_the_key(admin, openai):
    _, matches = await started_season(admin)
    openai.status = 401
    m = matches["AFC-WC-1"]
    await admin.post("/api/admin/agent/check", {"match_ids": [m["id"]]})
    assert (await run(openai))[0]["status"] == "ERROR"
    overview = await admin.get("/api/admin/agent/overview")
    assert KEY not in overview.text
    error = overview.json()["errors"][0]
    assert "401" in error["message"] and "sk-***" in error["message"]
    audit = (await admin.get("/api/admin/audit")).text
    assert KEY not in audit


def test_parse_response_rejects_garbage():
    with pytest.raises(result_agent.ResearchError):
        result_agent.parse_response({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}})
    with pytest.raises(result_agent.ResearchError):
        result_agent.parse_response({"status": "completed", "output": []})
    bad = {"type": "message", "content": [{"type": "output_text", "text": '{"status": "FINAL", "home_score": 300}'}]}
    with pytest.raises(result_agent.ResearchError):
        result_agent.parse_response({"status": "completed", "output": [bad]})
    assert result_agent.normalize_url("https://WWW.ESPN.com/a/b/?utm_source=x#y") == "espn.com/a/b"
    assert result_agent.normalize_url("https://espn.com/g?gameId=1&utm_medium=z") == "espn.com/g?gameId=1"
    assert result_agent.normalize_url("https://espn.com/g?gameId=1") != result_agent.normalize_url(
        "https://espn.com/g?gameId=2"
    )
    assert result_agent.normalize_url("javascript:alert(1)") is None


# ------------------------------------------------------------------ validation pipeline (unchanged rules)


def payload(match: dict, home: int, away: int, **extra) -> dict:
    return {
        "match_id": match["id"],
        "home_team": match["home_team"]["abbreviation"],
        "away_team": match["away_team"]["abbreviation"],
        "home_score": home,
        "away_score": away,
        "winner": match["home_team"]["abbreviation"] if home > away else match["away_team"]["abbreviation"],
        "source": "ESPN",
        "source_url": ESPN.format(match["id"]),
        "timestamp": iso(datetime.now(UTC)),
        "sources": [
            {"source": "NFL.com", "source_url": NFL.format(match["id"]), "home_score": home, "away_score": away}
        ],
        **extra,
    }


async def submit(body: dict) -> dict:
    async with get_sessionmaker()() as session:
        _, out = await process_result(session, result_agent.agent_principal(), body)
        return out


async def test_pipeline_validation(admin):
    env, matches = await started_season(admin)
    m = matches["AFC-WC-2"]
    for body in (
        {**payload(m, 28, 14), "match_id": 99999},
        {**payload(m, 28, 14), "home_team": "NE"},
        payload(m, 21, 21),
        {**payload(m, 28, 14), "winner": m["away_team"]["abbreviation"]},
        {**payload(m, 28, 14), "timestamp": iso(datetime.now(UTC) + timedelta(days=1))},
        {"match_id": m["id"], "home_score": "x"},
    ):
        assert (await submit(body))["status"] == "REJECTED", body
    swapped = {
        **payload(m, 14, 28),
        "home_team": m["away_team"]["abbreviation"],
        "away_team": m["home_team"]["abbreviation"],
        "winner": m["home_team"]["abbreviation"],
        "sources": [],
    }
    swapped["sources"] = [{"source": "NFL.com", "source_url": NFL.format(1), "home_score": 14, "away_score": 28}]
    out = await submit(swapped)
    assert out["status"] == "APPLIED" and "vertauscht" in out["message"]
    final_match = (await admin_matches(admin, env["season"]["id"]))["AFC-WC-2"]
    assert (final_match["home_score"], final_match["away_score"]) == (28, 14)
    # duplicates are ignored, deviations from a final result go to review
    assert (await submit(payload(m, 28, 14)))["status"] == "DUPLICATE"
    assert (await submit(payload(m, 27, 14)))["status"] == "REVIEW_REQUIRED"


async def test_game_not_started_is_rejected(admin):
    env = await setup_season(admin, kickoff_in=timedelta(hours=5))
    assert (await submit(payload(env["matches"]["AFC-WC-1"], 31, 24)))["status"] == "REJECTED"


async def test_points_and_bot_message(admin, players, openai):
    env = await setup_season(admin, kickoff_in=timedelta(hours=2))
    sid, t = env["season"]["id"], env["teams"]
    await pick(players["florian"], sid, "AFC-WC-1", t["BUF"], 31, 24)
    await pick(players["dennis"], sid, "AFC-WC-1", t["PIT"], 24, 10)
    m = env["matches"]["AFC-WC-1"]
    await admin.patch(f"/api/admin/matches/{m['id']}", {"kickoff_at": iso(datetime.now(UTC) - timedelta(hours=4))})
    await lock(admin, m["id"])
    openai.answers["BUF"] = final(31, 24, mid=m["id"])
    results = await run(openai)
    assert [r["status"] for r in results] == ["APPLIED"]
    board = (await players["florian"].get(f"/api/seasons/{sid}/leaderboard")).json()
    lb = {row["user"]["display_name"]: row for row in board}
    assert lb["Florian"]["points"] == 3 and lb["Dennis"]["points"] == 0
    chat = (await players["dennis"].get("/api/chat/messages")).json()
    final_msg = [c for c in chat if c["system"] and c["system"]["type"] == "FINAL"][-1]
    assert "Florian 🎯 +3" in final_msg["body"]
