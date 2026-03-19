"""Add refresh token rotation and token revocation tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_refresh_token_rotation"
down_revision = "f2a1c9b5d3e7"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    """Return whether the target table already exists in the current database."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _index_exists(table_name: str, index_name: str) -> bool:
    """Return whether the target index already exists on the given table."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    """Create refresh token rotation and revocation support tables."""

    if not _table_exists("refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_jti", sa.String(length=64), nullable=False),
            sa.Column("family_id", sa.String(length=64), nullable=False),
            sa.Column("replaced_by_jti", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _index_exists("refresh_tokens", op.f("ix_refresh_tokens_user_id")):
        op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)
    if not _index_exists("refresh_tokens", op.f("ix_refresh_tokens_token_jti")):
        op.create_index(op.f("ix_refresh_tokens_token_jti"), "refresh_tokens", ["token_jti"], unique=True)
    if not _index_exists("refresh_tokens", op.f("ix_refresh_tokens_family_id")):
        op.create_index(op.f("ix_refresh_tokens_family_id"), "refresh_tokens", ["family_id"], unique=False)

    if not _table_exists("revoked_tokens"):
        op.create_table(
            "revoked_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_jti", sa.String(length=64), nullable=False),
            sa.Column("token_type", sa.String(length=20), nullable=False),
            sa.Column("reason", sa.String(length=120), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not _index_exists("revoked_tokens", op.f("ix_revoked_tokens_user_id")):
        op.create_index(op.f("ix_revoked_tokens_user_id"), "revoked_tokens", ["user_id"], unique=False)
    if not _index_exists("revoked_tokens", op.f("ix_revoked_tokens_token_jti")):
        op.create_index(op.f("ix_revoked_tokens_token_jti"), "revoked_tokens", ["token_jti"], unique=True)


def downgrade() -> None:
    """Drop refresh token rotation and revocation support tables."""

    if _table_exists("revoked_tokens"):
        if _index_exists("revoked_tokens", op.f("ix_revoked_tokens_token_jti")):
            op.drop_index(op.f("ix_revoked_tokens_token_jti"), table_name="revoked_tokens")
        if _index_exists("revoked_tokens", op.f("ix_revoked_tokens_user_id")):
            op.drop_index(op.f("ix_revoked_tokens_user_id"), table_name="revoked_tokens")
        op.drop_table("revoked_tokens")

    if _table_exists("refresh_tokens"):
        if _index_exists("refresh_tokens", op.f("ix_refresh_tokens_family_id")):
            op.drop_index(op.f("ix_refresh_tokens_family_id"), table_name="refresh_tokens")
        if _index_exists("refresh_tokens", op.f("ix_refresh_tokens_token_jti")):
            op.drop_index(op.f("ix_refresh_tokens_token_jti"), table_name="refresh_tokens")
        if _index_exists("refresh_tokens", op.f("ix_refresh_tokens_user_id")):
            op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
        op.drop_table("refresh_tokens")
