"""add google oauth columns

Revision ID: f2a1c9b5d3e7
Revises: d7b1f8b2c3d4
Create Date: 2026-03-16 20:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2a1c9b5d3e7"
down_revision = "d7b1f8b2c3d4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("auth_provider", sa.String(length=32), server_default="local", nullable=False)
        )
        batch_op.add_column(sa.Column("google_sub", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("avatar_url", sa.String(length=512), nullable=True))
        batch_op.create_index(batch_op.f("ix_users_google_sub"), ["google_sub"], unique=True)


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_google_sub"))
        batch_op.drop_column("avatar_url")
        batch_op.drop_column("google_sub")
        batch_op.drop_column("auth_provider")
