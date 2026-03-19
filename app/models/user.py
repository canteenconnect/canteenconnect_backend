"""User model with hashed passwords and role ownership."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.payment import Payment
    from app.models.refresh_token import RefreshToken
    from app.models.revoked_token import RevokedToken
    from app.models.role import Role


class User(Base):
    """Application user that can access student or admin experiences."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    role_rel: Mapped["Role"] = relationship(back_populates="users")
    orders: Mapped[list["Order"]] = relationship(back_populates="student")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    revoked_tokens: Mapped[list["RevokedToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def role(self) -> str:
        """Expose the normalized role name for serialization and auth checks."""

        return self.role_rel.name.lower() if self.role_rel else ""
