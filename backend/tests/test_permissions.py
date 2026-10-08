import pytest

ADMIN_ENDPOINTS = [
    ("get", "/api/admin/users"),
    ("post", "/api/admin/users"),
    ("delete", "/api/admin/users/00000000-0000-0000-0000-000000000000"),
    ("post", "/api/admin/seasons"),
    ("get", "/api/admin/audit"),
    ("get", "/api/admin/agent/overview"),
    ("post", "/api/admin/agent/test"),
    ("get", "/api/admin/change-requests"),
    ("post", "/api/admin/matches/1/result"),
    ("post", "/api/admin/seasons/1/recalculate"),
    ("put", "/api/admin/teams/1"),
]


@pytest.mark.parametrize(("method", "url"), ADMIN_ENDPOINTS)
async def test_users_cannot_use_admin_endpoints(players, method, url):
    api = players["florian"]
    r = await getattr(api, method)(url, **({"json": {}} if method in {"post", "put"} else {}))
    assert r.status_code == 403


async def test_admin_can_manage_teams(admin):
    teams = (await admin.get("/api/teams")).json()
    kc = next(t for t in teams if t["abbreviation"] == "KC")
    body = {
        **{
            k: kc[k]
            for k in (
                "name",
                "short_name",
                "abbreviation",
                "city",
                "conference",
                "division",
                "primary_color",
                "secondary_color",
                "is_active",
            )
        },
        "logo_url": "https://cdn.example.org/kc.png",
        "primary_color": "#ff0000",
    }
    r = await admin.put(f"/api/admin/teams/{kc['id']}", body)
    assert r.status_code == 200 and r.json()["primary_color"] == "#ff0000"
    bad = {**body, "logo_url": "javascript:alert(1)"}
    assert (await admin.put(f"/api/admin/teams/{kc['id']}", bad)).status_code == 422
    r = await admin.post("/api/admin/teams", {**body, "abbreviation": "XX", "name": "Expansion Team"})
    assert r.status_code == 201


async def test_draft_seasons_hidden_from_users(admin, players):
    r = await admin.post("/api/admin/seasons", {"name": "2031/2032", "year": 2031})
    assert r.status_code == 201
    assert (await players["florian"].get("/api/seasons")).json() == []
    assert len((await admin.get("/api/seasons")).json()) == 1


async def test_admin_can_edit_season_identity(admin):
    season = (await admin.post("/api/admin/seasons", {"name": "2031/2032", "year": 2031})).json()
    r = await admin.patch(f"/api/admin/seasons/{season['id']}", {"name": "2032/2033", "year": 2032})
    assert r.status_code == 200
    assert r.json()["name"] == "2032/2033" and r.json()["year"] == 2032


async def test_only_one_active_season(admin):
    for year in (2031, 2032):
        await admin.post("/api/admin/seasons", {"name": f"{year}/{year + 1}", "year": year})
    seasons = {s["year"]: s["id"] for s in (await admin.get("/api/seasons")).json()}
    assert (await admin.post(f"/api/admin/seasons/{seasons[2031]}/activate")).status_code == 200
    assert (await admin.post(f"/api/admin/seasons/{seasons[2032]}/activate")).status_code == 409
