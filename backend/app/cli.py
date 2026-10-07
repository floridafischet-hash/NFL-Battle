"""Small management CLI.

docker compose exec backend python -m app.cli set-password <username> <new-password>
docker compose exec backend python -m app.cli create-admin <username> <password> [display name]
docker compose exec backend python -m app.cli list-users
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.db import dispose_engine, get_sessionmaker
from app.core.security import hash_password
from app.models import AuditLog, User
from app.models.enums import Role


async def set_password(username: str, password: str) -> int:
    async with get_sessionmaker()() as session:
        user = (await session.execute(select(User).where(User.username == username.lower()))).scalar_one_or_none()
        if user is None or user.is_bot:
            print(f"Benutzer '{username}' nicht gefunden", file=sys.stderr)
            return 1
        user.password_hash = hash_password(password)
        user.token_version += 1
        user.is_active = True
        session.add(
            AuditLog(
                actor_type="SYSTEM",
                actor_label="CLI",
                action="USER_PASSWORD_RESET",
                object_type="user",
                object_id=str(user.id),
                source="CLI",
            )
        )
        await session.commit()
    print(f"Passwort für '{username}' gesetzt (Benutzer aktiv, alte Logins abgemeldet).")
    return 0


async def create_admin(username: str, password: str, display: str = "Admin") -> int:
    async with get_sessionmaker()() as session:
        user = (await session.execute(select(User).where(User.username == username.lower()))).scalar_one_or_none()
        if user is None:
            user = User(username=username.lower(), display_name=display, role=Role.ADMIN, token_version=0)
            session.add(user)
        else:
            user.token_version += 1
        user.role = Role.ADMIN
        user.is_active = True
        user.password_hash = hash_password(password)
        await session.flush()
        session.add(
            AuditLog(
                actor_type="SYSTEM",
                actor_label="CLI",
                action="ADMIN_CREATED",
                object_type="user",
                object_id=str(user.id),
                source="CLI",
            )
        )
        await session.commit()
    print(f"Admin '{username}' ist bereit.")
    return 0


async def list_users() -> int:
    async with get_sessionmaker()() as session:
        for u in (await session.execute(select(User).where(User.is_bot.is_(False)).order_by(User.username))).scalars():
            print(f"{u.username:20} {u.display_name:20} {u.role.value:6} {'aktiv' if u.is_active else 'gesperrt'}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="NFL Bracket Battle – Verwaltung")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("set-password", help="Passwort eines Benutzers setzen")
    p.add_argument("username")
    p.add_argument("password")
    p = sub.add_parser("create-admin", help="Admin anlegen oder bestehenden Benutzer zum Admin machen")
    p.add_argument("username")
    p.add_argument("password")
    p.add_argument("display_name", nargs="?", default="Admin")
    sub.add_parser("list-users", help="Benutzer auflisten")
    args = parser.parse_args()

    async def run() -> int:
        try:
            if args.command == "set-password":
                return await set_password(args.username, args.password)
            if args.command == "create-admin":
                return await create_admin(args.username, args.password, args.display_name)
            return await list_users()
        finally:
            await dispose_engine()

    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
