from tests.conftest import create_user, login


async def test_only_the_instance_owner_manages_users(admin, players):
    await create_user("coadmin", __import__("app.models.enums", fromlist=["Role"]).Role.ADMIN)
    co = await login("coadmin")
    me = (await co.get("/api/me")).json()
    assert me["is_admin"] and not me["is_superuser"]
    assert (await admin.get("/api/me")).json()["is_superuser"] is True
    # a second admin can run the game but cannot create or manage users
    body = {"username": "neu", "display_name": "Neu", "password": "secret123"}
    assert (await co.post("/api/admin/users", body)).status_code == 403
    users = (await co.get("/api/admin/users")).json()
    florian = next(u for u in users if u["username"] == "florian")
    assert (await co.patch(f"/api/admin/users/{florian['id']}", {"role": "ADMIN"})).status_code == 403
    assert (await co.post(f"/api/admin/users/{florian['id']}/password", {"password": "hacked123"})).status_code == 403
    assert (await co.post("/api/admin/seasons", {"name": "2031/2032", "year": 2031})).status_code == 201
    # the owner can, and cannot be blocked or demoted
    assert (await admin.post("/api/admin/users", body)).status_code == 201
    owner = next(u for u in users if u["username"] == "admin")
    assert owner["is_superuser"] is True
    assert (await admin.patch(f"/api/admin/users/{owner['id']}", {"is_active": False})).status_code == 409
    assert (await admin.patch(f"/api/admin/users/{owner['id']}", {"role": "USER"})).status_code == 409
