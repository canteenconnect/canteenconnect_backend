"""add favorites table

Revision ID: d7b1f8b2c3d4
Revises: cbba5293a3ea
Create Date: 2026-03-11 20:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d7b1f8b2c3d4"
down_revision = "cbba5293a3ea"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "menu_item_id", name="ux_favorites_user_menu_item"),
    )
    with op.batch_alter_table("favorites") as batch_op:
        batch_op.create_index(batch_op.f("ix_favorites_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_favorites_menu_item_id"), ["menu_item_id"], unique=False)
        batch_op.create_index("ix_favorites_created_at", ["created_at"], unique=False)


def downgrade():
    with op.batch_alter_table("favorites") as batch_op:
        batch_op.drop_index("ix_favorites_created_at")
        batch_op.drop_index(batch_op.f("ix_favorites_menu_item_id"))
        batch_op.drop_index(batch_op.f("ix_favorites_user_id"))

    op.drop_table("favorites")
