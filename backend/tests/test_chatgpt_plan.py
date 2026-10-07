"""Provider "chatgpt": the Codex CLI signed in with a ChatGPT plan (here a fake `codex` script)."""

import json
import sys
import textwrap
from datetime import timedelta

import pytest

from app.core.config import get_settings
from app.services import result_agent
from tests.conftest import admin_matches, setup_season

FAKE_CODEX = textwrap.dedent(
    """
    import json, os, re, sys
    args = sys.argv[1:]
    home = os.environ["CODEX_HOME"]
    if args[:2] == ["login", "status"]:
        ok = os.path.exists(os.path.join(home, "auth.json"))
        print("Logged in using ChatGPT" if ok else "Not logged in")
        sys.exit(0 if ok else 1)
    assert args[0] == "exec" and "--json" in args and "--output-schema" in args
    assert any(a.startswith("tools.web_search.allowed_domains=") for a in args)
    assert "OPENAI_API_KEY" not in os.environ and "DATABASE_URL" not in os.environ
    out = args[args.index("--output-last-message") + 1]
    prompt = args[-1]
    home_team = re.search(r"Home team: .* \\((\\w+)\\)", prompt).group(1)
    away_team = re.search(r"Away team: .* \\((\\w+)\\)", prompt).group(1)
    results = json.load(open(os.path.join(home, "results.json")))
    score = results.get(home_team)
    urls = [f"https://www.espn.com/nfl/game/{home_team}", f"https://www.nfl.com/games/{home_team}"]
    print(json.dumps({"type": "thread.started", "thread_id": "t"}))
    print(json.dumps({"type": "item.completed", "item": {"id": "1", "type": "web_search", "query": "score",
        "action": {"type": "search", "sources": [{"type": "url", "url": u} for u in urls]}}}))
    answer = {"status": "FINAL", "home_team": home_team, "away_team": away_team, "home_score": score[0],
              "away_score": score[1], "winner": None, "note": "",
              "sources": [{"name": n, "url": u, "home_score": score[0], "away_score": score[1]}
                          for n, u in zip(["ESPN", "NFL.com"], urls)]}
    open(out, "w").write(json.dumps(answer))
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 7}}))
    """
)


@pytest.fixture
def codex(tmp_path, monkeypatch):
    script = tmp_path / "fake_codex.py"
    script.write_text(FAKE_CODEX)
    binary = tmp_path / "codex"
    binary.write_text(f'#!/bin/sh\nexec {sys.executable} {script} "$@"\n')
    binary.chmod(0o755)
    home = tmp_path / "codex-home"
    home.mkdir()
    settings = get_settings()
    monkeypatch.setattr(settings, "result_agent_provider", "chatgpt")
    monkeypatch.setattr(settings, "result_agent_enabled", True)
    monkeypatch.setattr(settings, "codex_bin", str(binary))
    monkeypatch.setattr(settings, "codex_home", str(home))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-reach-codex")
    return home


async def test_not_logged_in(admin, codex):
    assert not result_agent.is_configured()
    r = (await admin.post("/api/admin/agent/test")).json()
    assert r["ok"] is False and "codex login --device-auth" in r["message"]
    config = (await admin.get("/api/admin/agent/overview")).json()["config"]
    assert config["provider"] == "chatgpt" and config["chatgpt_login"] is False


async def test_results_via_chatgpt_plan(admin, codex):
    (codex / "auth.json").write_text("{}")
    env = await setup_season(admin, kickoff_in=timedelta(hours=-4))
    matches = env["matches"]
    (codex / "results.json").write_text(
        json.dumps({m["home_team"]["abbreviation"]: [27, 17] for m in matches.values() if m["home_team"]})
    )
    assert (await admin.post("/api/admin/agent/test")).json()["ok"] is True
    results = await result_agent.run_once()
    assert len(results) == 3 and {r["status"] for r in results} == {"APPLIED"}, results
    final = [m for m in (await admin_matches(admin, env["season"]["id"])).values() if m["status"] == "FINAL"]
    assert len(final) == 3 and all(m["result_source"] == "AGENT" for m in final)
    runs = (await admin.get("/api/admin/agent/overview")).json()["runs"]
    research = next(r for r in runs if r["kind"] == "RESEARCH")
    assert research["agent_label"] == "ChatGPT (ChatGPT-Abo)"
    assert research["request_payload"]["web_searches"] == 1
    assert len(research["request_payload"]["grounded_sources"]) == 2
