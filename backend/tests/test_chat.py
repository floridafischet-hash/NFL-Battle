import io
import time

from PIL import Image
from sqlalchemy import func, select
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.main import app
from app.models import ChatMessage, SystemMessage
from app.models.enums import SystemMessageType
from app.realtime.hub import hub
from app.services import bot
from tests.conftest import create_user, login


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


async def test_chat_post_list_delete(admin, players):
    florian, dennis = players["florian"], players["dennis"]
    r = await florian.post("/api/chat/messages", {"body": "  Go Bills! 🦬  "})
    assert r.status_code == 201
    msg = r.json()
    assert msg["body"] == "Go Bills! 🦬" and msg["user"]["display_name"] == "Florian" and msg["system"] is None
    assert (await florian.post("/api/chat/messages", {"body": "   "})).status_code == 422
    assert (await florian.post("/api/chat/messages", {"body": "x" * 1001})).status_code == 422
    # html is stored as plain text (rendered escaped by the client)
    r = await dennis.post("/api/chat/messages", {"body": "<script>alert(1)</script>"})
    assert r.json()["body"] == "<script>alert(1)</script>"
    listing = (await dennis.get("/api/chat/messages")).json()
    assert [m["body"] for m in listing][-2:] == ["Go Bills! 🦬", "<script>alert(1)</script>"]

    assert (await dennis.delete(f"/api/chat/messages/{msg['id']}")).status_code == 403
    assert (await florian.delete(f"/api/chat/messages/{msg['id']}")).status_code == 204
    other = listing[-1]["id"]
    assert (await admin.delete(f"/api/chat/messages/{other}")).status_code == 204
    listing = (await dennis.get("/api/chat/messages")).json()
    assert all(m["deleted"] for m in listing[-2:]) and listing[-1]["body"] == ""


async def test_chat_image_upload(players):
    florian = players["florian"]
    r = await florian.client.post(
        "/api/chat/uploads",
        files={"file": ("pic.png", png_bytes(), "image/png")},
        headers={"Authorization": f"Bearer {florian.token}"},
    )
    assert r.status_code == 201, r.text
    upload = r.json()
    assert upload["url"].endswith(".webp")
    r = await florian.post("/api/chat/messages", {"body": "", "upload_id": upload["id"]})
    assert r.status_code == 201 and r.json()["image_url"] == upload["url"]
    media = await florian.client.get(upload["url"])
    assert media.status_code == 200 and media.headers["content-type"] == "image/webp"
    assert "sandbox" in media.headers["content-security-policy"]
    # someone else cannot reuse the upload
    r = await players["dennis"].post("/api/chat/messages", {"body": "x", "upload_id": upload["id"]})
    assert r.status_code == 422
    # non-images are refused
    r = await florian.client.post(
        "/api/chat/uploads",
        files={"file": ("x.png", b"<svg onload=alert(1)>", "image/png")},
        headers={"Authorization": f"Bearer {florian.token}"},
    )
    assert r.status_code == 415


async def test_chat_rate_limit(players, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    codes = [(await players["stefan"].post("/api/chat/messages", {"body": f"spam {i}"})).status_code for i in range(22)]
    assert codes.count(201) == 20 and codes[-1] == 429


async def test_chat_bot_can_be_disabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "chat_bot_enabled", False)
    async with get_sessionmaker()() as session:
        assert await bot.post(session, SystemMessageType.INFO, "Automatische Nachricht") is None
        await session.commit()
        chat_count = (await session.execute(select(func.count(ChatMessage.id)))).scalar_one()
        system_count = (await session.execute(select(func.count(SystemMessage.id)))).scalar_one()
    assert chat_count == 0 and system_count == 0


async def test_websocket_receives_chat_live():
    await create_user("lisa")
    await create_user("kevin")
    lisa = await login("lisa")
    kevin = await login("kevin")
    with TestClient(app) as client:
        deadline = time.time() + 10
        while not hub.listening and time.time() < deadline:
            time.sleep(0.05)  # noqa: ASYNC251 - TestClient runs the app in its own thread
        assert hub.listening, "realtime listener did not connect"
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "auth", "token": lisa.token})
            assert ws.receive_json()["type"] == "ready"
            r = client.post(
                "/api/chat/messages",
                json={"body": "Live aus dem Stadion!"},
                headers={"Authorization": f"Bearer {kevin.token}"},
            )
            assert r.status_code == 201
            received = None
            for _ in range(10):
                event = ws.receive_json()
                if event["type"] == "chat_message":
                    received = event["message"]
                    break
            assert received is not None
            assert received["body"] == "Live aus dem Stadion!" and received["user"]["display_name"] == "Kevin"


async def test_websocket_rejects_missing_or_bad_token():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "auth", "token": "nope"})
            message = ws.receive()
            assert message["type"] == "websocket.close" and message["code"] == 4401
