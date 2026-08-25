"""add product moderation

Anyone signed in may offer an item; an administrator decides whether it
appears. Existing rows are back-filled as `approved`: they are the seeded
catalogue and were visible before this migration ran, so leaving them
`pending` would empty the shop on deploy.

Revision ID: a1b2c3d4e5f6
Revises: c8a39272abb5
Create Date: 2026-08-25 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "c8a39272abb5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        # server_default only for the back-fill of existing rows; the column
        # is NOT NULL and the application default is `pending`, so a new
        # listing is invisible until someone approves it.
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=16),
                nullable=False,
                server_default="approved",
            )
        )
        batch_op.add_column(sa.Column("moderation_note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint(
            "moderation_valid", "status IN ('pending','approved','rejected')"
        )
        batch_op.create_index("ix_products_status", ["status"], unique=False)
        batch_op.create_index("ix_products_moderation", ["status", "created_at"], unique=False)

    # Drop the server default now the back-fill is done, so the application
    # default (`pending`) is the only one that applies to new rows.
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.alter_column("status", server_default=None, existing_type=sa.String(length=16))


def downgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_index("ix_products_moderation")
        batch_op.drop_index("ix_products_status")
        batch_op.drop_constraint("moderation_valid", type_="check")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("moderation_note")
        batch_op.drop_column("status")
