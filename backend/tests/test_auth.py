from sqlalchemy import text

from app.core.db import get_sessionmaker
from app.models.enums import Role
from tests.conftest import Api, create_user, login


async def test_login_success_and_me():
    await create_user("florian")
    api = await login("Florian")  # username is case-insensitive
    r = await api.get("/api/me")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "florian" and body["role"] == "USER" and body["is_admin"] is False


async def test_login_wrong_password_and_unknown_user():
    await create_user("florian")
    api = Api()
    r = await api.post("/api/auth/login", {"username": "florian", "password": "wrong"})
    assert r.status_code == 401
    r = await api.post("/api/auth/login", {"username": "nobody", "password": "wrong"})
    assert r.status_code == 401


async def test_requires_authentication():
    api = Api()
    assert (await api.get("/api/me")).status_code == 401
    api.token = "garbage"
    assert (await api.get("/api/me")).status_code == 401


async def test_blocked_user_cannot_login_or_use_token(admin):
    await create_user("kevin")
    kevin = await login("kevin")
    users = (await admin.get("/api/admin/users")).json()
    kevin_id = next(u["id"] for u in users if u["username"] == "kevin")
    r = await admin.patch(f"/api/admin/users/{kevin_id}", {"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await kevin.get("/api/me")).status_code == 403
    r = await Api().post("/api/auth/login", {"username": "kevin", "password": "secret123"})
    assert r.status_code == 403


async def test_password_change_invalidates_old_tokens():
    await create_user("lisa")
    old = await login("lisa")
    r = await old.post("/api/me/password", {"current_password": "secret123", "new_password": "newpass99"})
    assert r.status_code == 200
    new_token = r.json()["access_token"]
    assert (await old.get("/api/me")).status_code == 401
    assert (await Api(new_token).get("/api/me")).status_code == 200
    await login("lisa", "newpass99")


async def test_admin_creates_user_and_resets_password(admin):
    r = await admin.post("/api/admin/users", {"username": "Marcel", "display_name": "Marcel", "password": "start123"})
    assert r.status_code == 201
    user_id = r.json()["id"]
    assert r.json()["username"] == "marcel"
    marcel = await login("marcel", "start123")
    r = await admin.post("/api/admin/users", {"username": "marcel", "display_name": "X", "password": "start123"})
    assert r.status_code == 409
    r = await admin.post(f"/api/admin/users/{user_id}/password", {"password": "reset456"})
    assert r.status_code == 204
    assert (await marcel.get("/api/me")).status_code == 401
    await login("marcel", "reset456")


async def test_role_change_takes_effect(admin):
    await create_user("tobi")
    tobi = await login("tobi")
    assert (await tobi.get("/api/admin/users")).status_code == 403
    users = (await admin.get("/api/admin/users")).json()
    tobi_id = next(u["id"] for u in users if u["username"] == "tobi")
    r = await admin.patch(f"/api/admin/users/{tobi_id}", {"role": "ADMIN"})
    assert r.status_code == 200
    assert (await tobi.get("/api/admin/users")).status_code == 200


async def test_admin_cannot_demote_or_block_self(admin):
    me = (await admin.get("/api/me")).json()
    assert (await admin.patch(f"/api/admin/users/{me['id']}", {"role": "USER"})).status_code == 409
    assert (await admin.patch(f"/api/admin/users/{me['id']}", {"is_active": False})).status_code == 409
    assert (await admin.delete(f"/api/admin/users/{me['id']}")).status_code == 409


async def test_admin_deletes_user_and_keeps_audit_history(admin):
    await create_user("kevin")
    kevin = await login("kevin")
    users = (await admin.get("/api/admin/users")).json()
    kevin_id = next(u["id"] for u in users if u["username"] == "kevin")

    r = await admin.delete(f"/api/admin/users/{kevin_id}")
    assert r.status_code == 204
    assert (await kevin.get("/api/me")).status_code == 401
    assert (await Api().post("/api/auth/login", {"username": "kevin", "password": "secret123"})).status_code == 401
    assert all(u["id"] != kevin_id for u in (await admin.get("/api/admin/users")).json())

    async with get_sessionmaker()() as session:
        deleted = (
            await session.execute(
                text("SELECT count(*) FROM audit_logs WHERE action = 'USER_DELETED' AND object_id = :user_id"),
                {"user_id": kevin_id},
            )
        ).scalar_one()
        assert deleted == 1


async def test_login_is_rate_limited(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    await create_user("stefan", Role.USER)
    api = Api()
    codes = [
        (await api.post("/api/auth/login", {"username": "stefan", "password": "wrong"})).status_code for _ in range(12)
    ]
    assert codes[0] == 401 and 429 in codes


async def test_audit_log_is_append_only(admin):
    async with get_sessionmaker()() as session:
        count = (await session.execute(text("SELECT count(*) FROM audit_logs"))).scalar_one()
        assert count >= 1  # login of the admin is audited
        try:
            await session.execute(text("UPDATE audit_logs SET action = 'X'"))
            raised = False
        except Exception:
            raised = True
        assert raised
