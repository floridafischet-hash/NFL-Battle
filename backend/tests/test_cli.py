from app.cli import create_admin, set_password
from app.models.enums import Role
from tests.conftest import Api, create_user, login


async def test_cli_set_password_and_create_admin():
    await create_user("kevin", active=False)
    assert await set_password("kevin", "fresh-pass") == 0
    await login("kevin", "fresh-pass")  # reactivated
    assert await set_password("nobody", "x") == 1

    assert await create_admin("chef", "chef-pass-1", "Chef") == 0
    chef = await login("chef", "chef-pass-1")
    assert (await chef.get("/api/admin/users")).status_code == 200
    # promoting an existing user
    await create_user("tobi", Role.USER)
    assert await create_admin("tobi", "tobi-admin-1") == 0
    tobi = Api((await login("tobi", "tobi-admin-1")).token)
    assert (await tobi.get("/api/me")).json()["role"] == "ADMIN"
