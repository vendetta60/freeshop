"""add location, needs, messaging, lending, emergency aid and notifications

FreeShop_Prompt phases 2 and 13.

SAFETY PROPERTIES OF THIS MIGRATION, stated because they are the whole
reason it is shaped the way it is:

* NOTHING IS DROPPED OR RENAMED. Every existing column and table survives
  untouched, so the release is reversible and the running application keeps
  working while it lands.

* EVERY ADDED COLUMN ON AN EXISTING TABLE IS NULLABLE OR HAS A SERVER
  DEFAULT. `products.transfer_type` back-fills to `giveaway`, which is what
  every listing on the board already is - the one value that cannot turn an
  existing gift into a loan. `order_request_items.outcome` back-fills to
  `pending`, which is exactly what those rows were: undecided.

* THE SERVER DEFAULTS ARE KEPT rather than dropped after the back-fill,
  unlike the moderation migration (a1b2c3d4e5f6) which dropped its own. That
  migration's back-fill value (`approved`) deliberately differed from the
  application default (`pending`), so leaving it would have published new
  listings by accident. Here the two agree, so the default is a harmless
  second line of defence.

* SQLite gets `batch_alter_table`, which rewrites the table - the only way to
  add a CHECK constraint on this database (plan.md 1, render_as_batch).

* No PostGIS, no spatial types. Coordinates are plain FLOATs with a composite
  index, and proximity is a bounding box plus Haversine in Python
  (app/services/geo.py). Moving to PostgreSQL later needs no change here.

Revision ID: b7c1d2e3f4a5
Revises: a1b2c3d4e5f6
Create Date: 2026-09-04 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1d2e3f4a5"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _location_columns(*, backfill: bool) -> list[sa.Column]:
    """The LocationMixin columns, as a migration sees them.

    Built by a helper rather than typed out four times: four hand-written
    copies is four chances for one table to get a different length or a
    different default, and a location column that behaves differently on
    needs than on listings is a bug nobody would look for.

    `backfill` adds the server defaults that existing ROWS need in order to
    satisfy NOT NULL. A brand-new table has no existing rows, so it takes
    none - and a server default the model does not declare would show up as
    drift on every future `alembic revision --autogenerate`.
    """
    return [
        sa.Column(
            "country",
            sa.String(length=2),
            nullable=False,
            server_default="AZ" if backfill else None,
        ),
        sa.Column("region", sa.String(length=80), nullable=True),
        sa.Column("city", sa.String(length=80), nullable=True),
        sa.Column("district", sa.String(length=80), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "location_precision",
            sa.String(length=10),
            nullable=False,
            server_default="none" if backfill else None,
        ),
    ]


def _timestamps() -> list[sa.Column]:
    """created_at / updated_at, spelled exactly as the initial migration
    spells them, so autogenerate sees no difference between the two."""
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ]


def _location_checks(table: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            "location_precision IN ('none','city','district')",
            name=f"{table}_precision_valid",
        ),
        sa.CheckConstraint(
            "latitude IS NULL OR (latitude BETWEEN -90 AND 90)", name=f"{table}_latitude_range"
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180 AND 180)",
            name=f"{table}_longitude_range",
        ),
    ]


def _add_location(table: str, prefix: str) -> None:
    with op.batch_alter_table(table, schema=None) as batch_op:
        for column in _location_columns(backfill=True):
            batch_op.add_column(column)
        for check in _location_checks(prefix):
            batch_op.create_check_constraint(check.name, check.sqltext)


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Location on the two existing tables that need it
    # -----------------------------------------------------------------------
    _add_location("users", "user")
    _add_location("products", "product")

    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "transfer_type", sa.String(length=10), nullable=False, server_default="giveaway"
            )
        )
        batch_op.add_column(sa.Column("available_from", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("available_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("max_borrow_days", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "transfer_type_valid", "transfer_type IN ('giveaway','loan')"
        )
        batch_op.create_check_constraint(
            "max_borrow_days_range",
            "max_borrow_days IS NULL OR max_borrow_days BETWEEN 1 AND 365",
        )
        batch_op.create_index("ix_products_transfer_type", ["transfer_type"], unique=False)
        batch_op.create_index("ix_products_geo", ["latitude", "longitude"], unique=False)
        batch_op.create_index(
            "ix_products_transfer", ["transfer_type", "status", "deleted_at"], unique=False
        )

    # -----------------------------------------------------------------------
    # 2. Per-line handover outcome (FreeShop_Prompt 5, Rule C)
    # -----------------------------------------------------------------------
    with op.batch_alter_table("order_request_items", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("outcome", sa.String(length=14), nullable=False, server_default="pending")
        )
        batch_op.add_column(sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint(
            "item_outcome_valid", "outcome IN ('pending','received','not_selected')"
        )
        batch_op.create_index(
            "ix_order_items_product_outcome", ["product_id", "outcome"], unique=False
        )

    # The server defaults above existed only to give EXISTING rows a value.
    # They are dropped now the back-fill is done, so the application default
    # is the only one that applies to new rows - the same discipline
    # a1b2c3d4e5f6 used, and what keeps `alembic revision --autogenerate`
    # from reporting drift against the models on every future run.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("country", server_default=None, existing_type=sa.String(length=2))
        batch_op.alter_column(
            "location_precision", server_default=None, existing_type=sa.String(length=10)
        )

    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.alter_column("country", server_default=None, existing_type=sa.String(length=2))
        batch_op.alter_column(
            "location_precision", server_default=None, existing_type=sa.String(length=10)
        )
        batch_op.alter_column(
            "transfer_type", server_default=None, existing_type=sa.String(length=10)
        )

    with op.batch_alter_table("order_request_items", schema=None) as batch_op:
        batch_op.alter_column("outcome", server_default=None, existing_type=sa.String(length=14))

    # -----------------------------------------------------------------------
    # 3. Needs (FreeShop_Prompt 4)
    # -----------------------------------------------------------------------
    op.create_table(
        "need_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("quantity_needed", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("moderation_status", sa.String(length=10), nullable=False),
        sa.Column("moderation_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("source_order_item_id", sa.Integer(), nullable=True),
        *_location_columns(backfill=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_order_item_id"], ["order_request_items.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "status IN ('open','partially_fulfilled','fulfilled','closed','expired')",
            name="need_status_valid",
        ),
        sa.CheckConstraint(
            "moderation_status IN ('pending','approved','rejected')", name="need_moderation_valid"
        ),
        sa.CheckConstraint("quantity_needed BETWEEN 1 AND 999", name="need_quantity_range"),
        *_location_checks("need"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_need_requests_user_id", "need_requests", ["user_id"])
    op.create_index("ix_need_requests_category_id", "need_requests", ["category_id"])
    op.create_index(
        "ix_need_requests_public", "need_requests", ["moderation_status", "status", "created_at"]
    )
    op.create_index("ix_need_requests_user", "need_requests", ["user_id", "created_at"])
    op.create_index("ix_need_requests_category", "need_requests", ["category_id", "status"])
    op.create_index("ix_need_requests_geo", "need_requests", ["latitude", "longitude"])

    # -----------------------------------------------------------------------
    # 4. Lending (FreeShop_Prompt 7)
    # -----------------------------------------------------------------------
    op.create_table(
        "loan_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("requested_days", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("borrowed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_return_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_note", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["borrower_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('pending','approved','borrowed','returned','rejected','cancelled')",
            name="loan_status_valid",
        ),
        sa.CheckConstraint(
            "requested_days IS NULL OR requested_days BETWEEN 1 AND 365", name="loan_days_range"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_loan_requests_product_id", "loan_requests", ["product_id"])
    op.create_index("ix_loan_requests_borrower_id", "loan_requests", ["borrower_id"])
    op.create_index("ix_loan_requests_product_status", "loan_requests", ["product_id", "status"])
    op.create_index("ix_loan_requests_borrower", "loan_requests", ["borrower_id", "created_at"])
    op.create_index("ix_loan_requests_due", "loan_requests", ["status", "expected_return_at"])

    # -----------------------------------------------------------------------
    # 5. Emergency aid (FreeShop_Prompt 8)
    # -----------------------------------------------------------------------
    op.create_table(
        "emergency_aid_cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title_az", sa.String(length=200), nullable=False),
        sa.Column("title_en", sa.String(length=200), nullable=True),
        sa.Column("description_az", sa.Text(), nullable=False),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("beneficiary_display_name", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        # Admin-only for the life of this table. Never selected by a public
        # DTO - see app/schemas/emergency.py.
        sa.Column("verification_note_internal", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        *_location_columns(backfill=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["users.id"]),
        sa.CheckConstraint(
            "status IN ('draft','active','paused','completed','cancelled')",
            name="case_status_valid",
        ),
        *_location_checks("case"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emergency_aid_cases_slug", "emergency_aid_cases", ["slug"], unique=True)
    op.create_index(
        "ix_emergency_aid_cases_created_by_admin_id", "emergency_aid_cases", ["created_by_admin_id"]
    )
    op.create_index("ix_emergency_cases_public", "emergency_aid_cases", ["status", "published_at"])

    op.create_table(
        "emergency_aid_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("emergency_case_id", sa.Integer(), nullable=False),
        sa.Column("title_az", sa.String(length=200), nullable=False),
        sa.Column("title_en", sa.String(length=200), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("quantity_needed", sa.Integer(), nullable=False),
        sa.Column("quantity_committed", sa.Integer(), nullable=False),
        sa.Column("quantity_received", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["emergency_case_id"], ["emergency_aid_cases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.CheckConstraint("priority IN ('urgent','normal','low')", name="aid_priority_valid"),
        sa.CheckConstraint("quantity_needed BETWEEN 1 AND 999", name="aid_quantity_range"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_emergency_aid_items_emergency_case_id", "emergency_aid_items", ["emergency_case_id"]
    )
    op.create_index(
        "ix_aid_items_case_order", "emergency_aid_items", ["emergency_case_id", "sort_order"]
    )

    op.create_table(
        "aid_commitments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["item_id"], ["emergency_aid_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('offered','accepted','received','cancelled')",
            name="commitment_status_valid",
        ),
        sa.CheckConstraint("quantity BETWEEN 1 AND 999", name="commitment_quantity_range"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aid_commitments_item_id", "aid_commitments", ["item_id"])
    op.create_index("ix_aid_commitments_user_id", "aid_commitments", ["user_id"])
    op.create_index("ix_commitments_item_status", "aid_commitments", ["item_id", "status"])
    op.create_index("ix_commitments_user", "aid_commitments", ["user_id", "created_at"])

    # -----------------------------------------------------------------------
    # 6. Messaging (FreeShop_Prompt 3)
    #
    # Created AFTER everything it can point at, because a conversation's
    # context is a real foreign key rather than an untyped (type, id) pair.
    # -----------------------------------------------------------------------
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=12), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("need_id", sa.Integer(), nullable=True),
        sa.Column("loan_id", sa.Integer(), nullable=True),
        sa.Column("emergency_case_id", sa.Integer(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["listing_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["need_id"], ["need_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loan_id"], ["loan_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["emergency_case_id"], ["emergency_aid_cases.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "type IN ('listing','need','loan','emergency')", name="conversation_type_valid"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_listing", "conversations", ["listing_id"])
    op.create_index("ix_conversations_need", "conversations", ["need_id"])
    op.create_index("ix_conversations_loan", "conversations", ["loan_id"])
    op.create_index("ix_conversations_emergency", "conversations", ["emergency_case_id"])
    op.create_index("ix_conversations_recent", "conversations", ["last_message_at"])

    op.create_table(
        "conversation_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # The membership row IS the authorisation, so it must be unique - two
        # rows for one person would make "am I in this thread?" ambiguous.
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_participant_once"),
    )
    op.create_index(
        "ix_conversation_participants_conversation_id",
        "conversation_participants",
        ["conversation_id"],
    )
    op.create_index(
        "ix_conversation_participants_user_id", "conversation_participants", ["user_id"]
    )
    op.create_index(
        "ix_participants_user", "conversation_participants", ["user_id", "conversation_id"]
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
    op.create_index("ix_messages_thread", "messages", ["conversation_id", "id"])
    op.create_index("ix_messages_unread", "messages", ["conversation_id", "created_at"])

    # -----------------------------------------------------------------------
    # 7. Notifications (FreeShop_Prompt 12)
    # -----------------------------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("link", sa.String(length=200), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_unread", "notifications", ["user_id", "read_at"])
    op.create_index("ix_notifications_feed", "notifications", ["user_id", "created_at"])


def downgrade() -> None:
    """Exactly the inverse, newest table first.

    Dropped in reverse dependency order so no foreign key outlives what it
    points at - SQLite will not complain, PostgreSQL will.
    """
    op.drop_table("notifications")
    op.drop_table("messages")
    op.drop_table("conversation_participants")
    op.drop_table("conversations")
    op.drop_table("aid_commitments")
    op.drop_table("emergency_aid_items")
    op.drop_table("emergency_aid_cases")
    op.drop_table("loan_requests")
    op.drop_table("need_requests")

    with op.batch_alter_table("order_request_items", schema=None) as batch_op:
        batch_op.drop_index("ix_order_items_product_outcome")
        batch_op.drop_constraint("item_outcome_valid", type_="check")
        batch_op.drop_column("decided_at")
        batch_op.drop_column("outcome")

    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_index("ix_products_transfer")
        batch_op.drop_index("ix_products_geo")
        batch_op.drop_index("ix_products_transfer_type")
        batch_op.drop_constraint("max_borrow_days_range", type_="check")
        batch_op.drop_constraint("transfer_type_valid", type_="check")
        batch_op.drop_column("max_borrow_days")
        batch_op.drop_column("available_until")
        batch_op.drop_column("available_from")
        batch_op.drop_column("transfer_type")

    for table, prefix in (("products", "product"), ("users", "user")):
        with op.batch_alter_table(table, schema=None) as batch_op:
            for check in _location_checks(prefix):
                batch_op.drop_constraint(check.name, type_="check")
            for column in (
                "location_precision",
                "longitude",
                "latitude",
                "district",
                "city",
                "region",
                "country",
            ):
                batch_op.drop_column(column)
