async def test_admin_sets_the_king_everyone_sees_it(admin, players):
    assert (await players["florian"].get("/api/greeting")).json() == {"king_name": None, "king_title": "König"}
    assert (await players["florian"].put("/api/admin/greeting", {"king_name": "Dennis"})).status_code == 403
    r = await admin.put("/api/admin/greeting", {"king_name": "  Dennis  ", "king_title": "König 2025"})
    assert r.status_code == 200 and r.json() == {"king_name": "Dennis", "king_title": "König 2025"}
    assert (await players["stefan"].get("/api/greeting")).json()["king_name"] == "Dennis"
    assert (await admin.put("/api/admin/greeting", {"king_name": "Den‮nis"})).status_code == 422
    # empty clears it
    r = await admin.put("/api/admin/greeting", {"king_name": "", "king_title": ""})
    assert r.json() == {"king_name": None, "king_title": "König"}
    audit = (await admin.get("/api/admin/audit", params={"action": "GREETING_UPDATED"})).json()["items"]
    assert len(audit) == 2
