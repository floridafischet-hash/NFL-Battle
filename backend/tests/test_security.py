"""Hardening: login lockout, name sanitizing, uploads, change-request timing, draft seasons."""

import io
from datetime import timedelta

from PIL import Image

from app.core.config import get_settings
from tests.conftest import Api, create_user, lock, result, setup_season


async def test_failed_logins_lock_only_the_attacker(admin, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    await create_user("victim")
    for _ in range(10):
        r = await Api().post("/api/auth/login", {"username": "victim", "password": "wrong"})
        assert r.status_code == 401
    r = await Api().post("/api/auth/login", {"username": "victim", "password": "wrong"})
    assert r.status_code == 429 and "Retry-After" in r.headers
    # the same account from another IP is still usable (no lockout of friends)
    r = await Api().post(
        "/api/auth/login", {"username": "victim", "password": "secret123"}, headers={"X-Real-IP": "203.0.113.9"}
    )
    assert r.status_code == 200
    # successful logins are not counted at all (the general per-IP limit of 20 / 5 min still applies)
    for _ in range(5):
        r = await Api().post(
            "/api/auth/login", {"username": "victim", "password": "secret123"}, headers={"X-Real-IP": "203.0.113.9"}
        )
        assert r.status_code == 200


async def test_display_names_reject_invisible_characters(admin):
    r = await admin.patch("/api/me", {"display_name": "Flo‮rian"})
    assert r.status_code == 422
    r = await admin.patch("/api/me", {"display_name": "  Flo   rian  "})
    assert r.status_code == 200 and r.json()["display_name"] == "Flo rian"
    r = await admin.post("/api/admin/users", {"username": "zw", "display_name": "Den​nis", "password": "secret123"})
    assert r.status_code == 422


async def test_huge_images_are_refused(admin):
    buf = io.BytesIO()
    Image.new("1", (5000, 5000)).save(buf, format="PNG")  # tiny file, 25 megapixels
    r = await admin.post("/api/me/avatar", files={"file": ("bomb.png", buf.getvalue(), "image/png")})
    assert r.status_code in (413, 415)
    ok = io.BytesIO()
    Image.new("RGB", (64, 64), "red").save(ok, format="PNG")
    r = await admin.post("/api/me/avatar", files={"file": ("a.png", ok.getvalue(), "image/png")})
    assert r.status_code == 200 and r.json()["avatar_url"].endswith(".webp")


async def test_change_requests_only_before_kickoff_and_never_after_final(admin, players):
    env = await setup_season(admin, kickoff_in=timedelta(hours=2))
    m, t = env["matches"]["AFC-WC-1"], env["teams"]
    await lock(admin, m["id"])
    r = await players["florian"].post(f"/api/matches/{m['id']}/change-requests", {"winner_team_id": t["BUF"]})
    assert r.status_code == 201, r.text
    request_id = r.json()["id"]
    await admin.patch(f"/api/admin/matches/{m['id']}", {"kickoff_at": "2000-01-01T00:00:00Z"})
    r = await players["dennis"].post(f"/api/matches/{m['id']}/change-requests", {"winner_team_id": t["BUF"]})
    assert r.status_code == 409  # game already running
    await result(admin, m["id"], 31, 24)
    r = await admin.post(f"/api/admin/change-requests/{request_id}/approve", {})
    assert r.status_code == 409  # result known: approving would allow cheating
    assert (await admin.post(f"/api/admin/change-requests/{request_id}/reject", {})).status_code == 200


async def test_draft_seasons_are_hidden_from_players(admin, players):
    r = await admin.post("/api/admin/seasons", {"name": "2031/2032", "year": 2031})
    draft = r.json()
    assert (await players["florian"].get(f"/api/seasons/{draft['id']}/matches")).status_code == 404
    assert (await players["florian"].get(f"/api/seasons/{draft['id']}/bracket/me")).status_code == 404
    assert (await admin.get(f"/api/seasons/{draft['id']}/matches")).status_code == 200


async def test_api_docs_disabled_in_production(monkeypatch):
    from app.main import create_app

    monkeypatch.setattr(get_settings(), "app_env", "production")
    app = create_app()
    assert app.docs_url is None and app.openapi_url is None
