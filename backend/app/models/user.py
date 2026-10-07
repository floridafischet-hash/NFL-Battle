import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import Role


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # bumped on password change / logout-everywhere -> invalidates all issued tokens
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[Role] = mapped_column(str_enum(Role, "user_role"), default=Role.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # the account that set up the instance (ADMIN_USERNAME): only it may create/manage users
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN
