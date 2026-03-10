"""initial production schema

Revision ID: cbba5293a3ea
Revises:
Create Date: 2026-03-10 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cbba5293a3ea"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("roles") as batch_op:
        batch_op.create_index(batch_op.f("ix_roles_name"), ["name"], unique=True)

    op.create_table(
        "campuses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("campuses") as batch_op:
        batch_op.create_index(batch_op.f("ix_campuses_code"), ["code"], unique=True)
        batch_op.create_index(batch_op.f("ix_campuses_name"), ["name"], unique=True)

    op.create_table(
        "outlets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campus_id", "name", name="ix_outlets_campus_id_name"),
    )
    with op.batch_alter_table("outlets") as batch_op:
        batch_op.create_index(batch_op.f("ix_outlets_campus_id"), ["campus_id"], unique=False)

    op.create_table(
        "menu_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("available_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_available", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("menu_items") as batch_op:
        batch_op.create_index("ix_menu_items_outlet_id_name", ["outlet_id", "name"], unique=False)
        batch_op.create_index(batch_op.f("ix_menu_items_outlet_id"), ["outlet_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_menu_items_is_available"), ["is_available"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=True),
        sa.Column("roll_number", sa.String(length=64), nullable=True),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=True)
        batch_op.create_index(batch_op.f("ix_users_roll_number"), ["roll_number"], unique=True)
        batch_op.create_index("ix_users_role_id", ["role_id"], unique=False)
        batch_op.create_index("ix_users_campus_id", ["campus_id"], unique=False)
        batch_op.create_index("ix_users_outlet_id", ["outlet_id"], unique=False)

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_number", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("payment_status", sa.String(length=24), nullable=False, server_default="CREATED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number"),
    )
    with op.batch_alter_table("orders") as batch_op:
        batch_op.create_index("ix_orders_created_at", ["created_at"], unique=False)
        batch_op.create_index("ix_orders_outlet_id", ["outlet_id"], unique=False)
        batch_op.create_index("ix_orders_status", ["status"], unique=False)
        batch_op.create_index("ix_orders_user_id", ["user_id"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("order_items") as batch_op:
        batch_op.create_index(batch_op.f("ix_order_items_menu_item_id"), ["menu_item_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_order_items_order_id"), ["order_id"], unique=False)

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="INR", nullable=False),
        sa.Column("gateway", sa.String(length=32), nullable=False),
        sa.Column("gateway_order_id", sa.String(length=120), nullable=True),
        sa.Column("gateway_payment_id", sa.String(length=120), nullable=True),
        sa.Column("gateway_signature", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("payments") as batch_op:
        batch_op.create_index(batch_op.f("ix_payments_order_id"), ["order_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_payments_user_id"), ["user_id"], unique=False)
        batch_op.create_index("ix_payments_gateway_order_id", ["gateway_order_id"], unique=False)
        batch_op.create_index("ix_payments_gateway_payment_id", ["gateway_payment_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_payments_status"), ["status"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("payment_gateway", sa.String(length=32), nullable=False),
        sa.Column("gateway_transaction_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gateway_transaction_id"),
    )
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.create_index(batch_op.f("ix_transactions_order_id"), ["order_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_transactions_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_transactions_status"), ["status"], unique=False)
        batch_op.create_index("ix_transactions_created_at", ["created_at"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.create_index(batch_op.f("ix_audit_logs_user_id"), ["user_id"], unique=False)
        batch_op.create_index("ix_audit_logs_created_at", ["created_at"], unique=False)

    op.create_table(
        "token_blocklist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("token_type", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("token_blocklist") as batch_op:
        batch_op.create_index(batch_op.f("ix_token_blocklist_jti"), ["jti"], unique=True)
        batch_op.create_index(batch_op.f("ix_token_blocklist_user_id"), ["user_id"], unique=False)


def downgrade():
    with op.batch_alter_table("token_blocklist") as batch_op:
        batch_op.drop_index(batch_op.f("ix_token_blocklist_user_id"))
        batch_op.drop_index(batch_op.f("ix_token_blocklist_jti"))

    op.drop_table("token_blocklist")
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_index("ix_audit_logs_created_at")
        batch_op.drop_index(batch_op.f("ix_audit_logs_user_id"))

    op.drop_table("audit_logs")
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_index("ix_transactions_created_at")
        batch_op.drop_index(batch_op.f("ix_transactions_status"))
        batch_op.drop_index(batch_op.f("ix_transactions_user_id"))
        batch_op.drop_index(batch_op.f("ix_transactions_order_id"))

    op.drop_table("transactions")
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_index(batch_op.f("ix_payments_status"))
        batch_op.drop_index("ix_payments_gateway_payment_id")
        batch_op.drop_index("ix_payments_gateway_order_id")
        batch_op.drop_index(batch_op.f("ix_payments_user_id"))
        batch_op.drop_index(batch_op.f("ix_payments_order_id"))

    op.drop_table("payments")
    with op.batch_alter_table("order_items") as batch_op:
        batch_op.drop_index(batch_op.f("ix_order_items_order_id"))
        batch_op.drop_index(batch_op.f("ix_order_items_menu_item_id"))

    op.drop_table("order_items")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_index("ix_orders_user_id")
        batch_op.drop_index("ix_orders_status")
        batch_op.drop_index("ix_orders_outlet_id")
        batch_op.drop_index("ix_orders_created_at")

    op.drop_table("orders")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_outlet_id")
        batch_op.drop_index("ix_users_campus_id")
        batch_op.drop_index("ix_users_role_id")
        batch_op.drop_index(batch_op.f("ix_users_roll_number"))
        batch_op.drop_index(batch_op.f("ix_users_email"))

    op.drop_table("users")
    with op.batch_alter_table("menu_items") as batch_op:
        batch_op.drop_index(batch_op.f("ix_menu_items_is_available"))
        batch_op.drop_index(batch_op.f("ix_menu_items_outlet_id"))
        batch_op.drop_index("ix_menu_items_outlet_id_name")

    op.drop_table("menu_items")
    with op.batch_alter_table("outlets") as batch_op:
        batch_op.drop_index(batch_op.f("ix_outlets_campus_id"))

    op.drop_table("outlets")
    with op.batch_alter_table("campuses") as batch_op:
        batch_op.drop_index(batch_op.f("ix_campuses_name"))
        batch_op.drop_index(batch_op.f("ix_campuses_code"))

    op.drop_table("campuses")
    with op.batch_alter_table("roles") as batch_op:
        batch_op.drop_index(batch_op.f("ix_roles_name"))

    op.drop_table("roles")
