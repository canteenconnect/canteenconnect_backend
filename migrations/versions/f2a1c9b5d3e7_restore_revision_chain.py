"""Restore the historical revision referenced by production databases."""

from __future__ import annotations

revision = "f2a1c9b5d3e7"
down_revision = "0001_fastapi_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op bridge revision retained for production migration continuity."""

    return None


def downgrade() -> None:
    """No-op downgrade for the restored bridge revision."""

    return None
