"""Adapt legacy Flask-era tables to the current FastAPI schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_legacy_schema_compat"
down_revision = "0002_refresh_token_rotation"
branch_labels = None
depends_on = None

ROLE_DESCRIPTIONS = {
    "admin": "Platform administrator with full management access.",
    "super_admin": "Executive administrator with cross-campus visibility.",
    "campus_admin": "Campus-level operations administrator.",
    "vendor_manager": "Vendor operations manager with outlet visibility.",
    "kitchen_staff": "Kitchen operations staff for fulfillment workflows.",
    "student": "Student account for browsing menus and placing orders.",
}


def _inspector() -> sa.Inspector:
    """Return a fresh inspector after each schema mutation."""

    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    """Return whether the target table exists."""

    return _inspector().has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    """Return the set of column names for a table."""

    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in _inspector().get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    """Return whether an index exists on a table."""

    if not _table_exists(table_name):
        return False
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def _foreign_key_name(
    table_name: str,
    constrained_columns: list[str],
    referred_table: str | None = None,
) -> str | None:
    """Return the name of a matching foreign key if it exists."""

    if not _table_exists(table_name):
        return None

    for foreign_key in _inspector().get_foreign_keys(table_name):
        if foreign_key.get("constrained_columns") != constrained_columns:
            continue
        if referred_table is not None and foreign_key.get("referred_table") != referred_table:
            continue
        return foreign_key.get("name")
    return None


def _ensure_roles_table() -> None:
    """Create and seed the RBAC roles table when missing."""

    if not _table_exists("roles"):
        op.create_table(
            "roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _index_exists("roles", op.f("ix_roles_name")):
        op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)

    for name, description in ROLE_DESCRIPTIONS.items():
        op.execute(
            sa.text(
                """
                INSERT INTO roles (name, description)
                VALUES (:name, :description)
                ON CONFLICT (name) DO UPDATE
                SET description = EXCLUDED.description
                """
            ).bindparams(name=name, description=description)
        )


def _migrate_users_table() -> None:
    """Bring the legacy users table forward to the FastAPI structure."""

    columns = _column_names("users")

    if "name" in columns and "full_name" not in columns:
        op.alter_column(
            "users",
            "name",
            new_column_name="full_name",
            existing_type=sa.String(length=120),
            existing_nullable=False,
        )
        columns = _column_names("users")

    if "password_hash" in columns and "hashed_password" not in columns:
        op.alter_column(
            "users",
            "password_hash",
            new_column_name="hashed_password",
            existing_type=sa.String(length=255),
            existing_nullable=False,
        )
        columns = _column_names("users")

    if "username" not in columns:
        op.add_column("users", sa.Column("username", sa.String(length=50), nullable=True))
        columns = _column_names("users")

    if "full_name" not in columns:
        op.add_column("users", sa.Column("full_name", sa.String(length=120), nullable=True))
        columns = _column_names("users")

    if "hashed_password" not in columns:
        op.add_column("users", sa.Column("hashed_password", sa.String(length=255), nullable=True))
        columns = _column_names("users")

    if "is_active" not in columns:
        op.add_column(
            "users",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        columns = _column_names("users")

    if "role_id" not in columns:
        op.add_column("users", sa.Column("role_id", sa.Integer(), nullable=True))
        columns = _column_names("users")

    if "updated_at" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        columns = _column_names("users")

    if "created_at" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        columns = _column_names("users")

    if "role" in columns:
        op.alter_column(
            "users",
            "role",
            existing_type=sa.String(length=32),
            nullable=False,
            server_default=sa.text("'student'"),
        )

    role_source = "users.role" if "role" in columns else "'student'"

    op.execute(
        sa.text(
            """
            UPDATE users
            SET full_name = COALESCE(NULLIF(full_name, ''), split_part(email, '@', 1))
            WHERE full_name IS NULL OR btrim(full_name) = ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET username = lower(split_part(email, '@', 1)) || '_' || id
            WHERE username IS NULL OR btrim(username) = ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET hashed_password = COALESCE(hashed_password, '')
            WHERE hashed_password IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET updated_at = COALESCE(updated_at, created_at, now())
            WHERE updated_at IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE users
            SET role_id = roles.id
            FROM roles
            WHERE users.role_id IS NULL
              AND roles.name = CASE lower(COALESCE({role_source}, 'student'))
                WHEN 'admin' THEN 'admin'
                WHEN 'executive' THEN 'super_admin'
                WHEN 'kitchen' THEN 'kitchen_staff'
                WHEN 'vendor' THEN 'vendor_manager'
                WHEN 'vendor_manager' THEN 'vendor_manager'
                WHEN 'campus_admin' THEN 'campus_admin'
                WHEN 'super_admin' THEN 'super_admin'
                ELSE 'student'
              END
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET role_id = roles.id
            FROM roles
            WHERE users.role_id IS NULL
              AND roles.name = 'student'
            """
        )
    )

    op.alter_column("users", "username", existing_type=sa.String(length=50), nullable=False)
    op.alter_column("users", "full_name", existing_type=sa.String(length=120), nullable=False)
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("users", "role_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "users",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )

    if not _index_exists("users", op.f("ix_users_username")):
        op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    if not _index_exists("users", op.f("ix_users_role_id")):
        op.create_index(op.f("ix_users_role_id"), "users", ["role_id"], unique=False)

    role_fk = _foreign_key_name("users", ["role_id"], "roles")
    if role_fk is None:
        op.create_foreign_key(
            op.f("fk_users_role_id_roles"),
            "users",
            "roles",
            ["role_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def _migrate_outlets_table() -> None:
    """Ensure outlets include the FastAPI update timestamp."""

    columns = _column_names("outlets")
    if "updated_at" not in columns:
        op.add_column(
            "outlets",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
    op.execute(
        sa.text(
            """
            UPDATE outlets
            SET updated_at = COALESCE(updated_at, created_at, now())
            WHERE updated_at IS NULL
            """
        )
    )


def _migrate_menu_items_table() -> None:
    """Rename legacy menu columns to the new FastAPI names."""

    columns = _column_names("menu_items")

    if "item_name" in columns and "name" not in columns:
        op.alter_column(
            "menu_items",
            "item_name",
            new_column_name="name",
            existing_type=sa.String(length=120),
            existing_nullable=False,
        )
        columns = _column_names("menu_items")

    if "available_quantity" in columns and "stock_quantity" not in columns:
        op.alter_column(
            "menu_items",
            "available_quantity",
            new_column_name="stock_quantity",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        columns = _column_names("menu_items")

    if "name" not in columns:
        op.add_column("menu_items", sa.Column("name", sa.String(length=120), nullable=True))
        columns = _column_names("menu_items")

    if "stock_quantity" not in columns:
        op.add_column(
            "menu_items",
            sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"),
        )
        columns = _column_names("menu_items")

    if "updated_at" not in columns:
        op.add_column(
            "menu_items",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    op.execute(
        sa.text(
            """
            UPDATE menu_items
            SET name = COALESCE(NULLIF(name, ''), 'item_' || id)
            WHERE name IS NULL OR btrim(name) = ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE menu_items
            SET updated_at = COALESCE(updated_at, created_at, now())
            WHERE updated_at IS NULL
            """
        )
    )
    op.alter_column("menu_items", "name", existing_type=sa.String(length=120), nullable=False)
    op.alter_column(
        "menu_items",
        "stock_quantity",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="0",
    )
    if not _index_exists("menu_items", op.f("ix_menu_items_name")):
        op.create_index(op.f("ix_menu_items_name"), "menu_items", ["name"], unique=False)


def _migrate_orders_table() -> None:
    """Convert legacy order ownership and payment metadata columns."""

    columns = _column_names("orders")

    if "user_id" in columns and "student_id" not in columns:
        user_fk = _foreign_key_name("orders", ["user_id"])
        if user_fk is not None:
            op.drop_constraint(user_fk, "orders", type_="foreignkey")
        op.alter_column(
            "orders",
            "user_id",
            new_column_name="student_id",
            existing_type=sa.Integer(),
            existing_nullable=True,
        )
        columns = _column_names("orders")

    if "student_id" not in columns:
        op.add_column("orders", sa.Column("student_id", sa.Integer(), nullable=True))
        columns = _column_names("orders")

    if "payment_status" not in columns:
        op.add_column(
            "orders",
            sa.Column("payment_status", sa.String(length=20), nullable=False, server_default="pending"),
        )
        columns = _column_names("orders")

    if "updated_at" not in columns:
        op.add_column(
            "orders",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        columns = _column_names("orders")

    if "payment_mode" in columns:
        op.alter_column(
            "orders",
            "payment_mode",
            existing_type=sa.String(length=20),
            nullable=False,
            server_default=sa.text("'cash'"),
        )

    student_fk = _foreign_key_name("orders", ["student_id"], "students")
    if student_fk is not None:
        op.drop_constraint(student_fk, "orders", type_="foreignkey")

    if "student_id" in columns and _table_exists("students"):
        op.execute(
            sa.text(
                """
                UPDATE orders
                SET student_id = students.user_id
                FROM students
                WHERE students.id = orders.student_id
                """
            )
        )

    completed_at_source = "completed_at" if "completed_at" in columns else "created_at"
    op.execute(
        sa.text(
            f"""
            UPDATE orders
            SET updated_at = COALESCE(updated_at, {completed_at_source}, created_at, now())
            WHERE updated_at IS NULL
            """
        )
    )

    if not _index_exists("orders", op.f("ix_orders_student_id")):
        op.create_index(op.f("ix_orders_student_id"), "orders", ["student_id"], unique=False)

    order_student_fk = _foreign_key_name("orders", ["student_id"], "users")
    if "student_id" in _column_names("orders") and order_student_fk is None:
        op.create_foreign_key(
            op.f("fk_orders_student_id_users"),
            "orders",
            "users",
            ["student_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def _migrate_order_items_table() -> None:
    """Rename legacy order item pricing columns."""

    columns = _column_names("order_items")

    if "price" in columns and "unit_price" not in columns:
        op.alter_column(
            "order_items",
            "price",
            new_column_name="unit_price",
            existing_type=sa.Numeric(precision=10, scale=2),
            existing_nullable=False,
        )
        columns = _column_names("order_items")

    if "unit_price" not in columns:
        op.add_column(
            "order_items",
            sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=True),
        )
        columns = _column_names("order_items")

    if "line_total" not in columns:
        op.add_column(
            "order_items",
            sa.Column("line_total", sa.Numeric(precision=10, scale=2), nullable=True),
        )

    op.execute(
        sa.text(
            """
            UPDATE order_items
            SET line_total = COALESCE(line_total, quantity * unit_price)
            WHERE line_total IS NULL
            """
        )
    )
    op.alter_column(
        "order_items",
        "unit_price",
        existing_type=sa.Numeric(precision=10, scale=2),
        nullable=False,
    )
    op.alter_column(
        "order_items",
        "line_total",
        existing_type=sa.Numeric(precision=10, scale=2),
        nullable=False,
    )


def _migrate_payments_table() -> None:
    """Rename legacy payment columns and backfill new ownership metadata."""

    columns = _column_names("payments")
    order_columns = _column_names("orders")

    if "payment_status" in columns and "status" not in columns:
        op.alter_column(
            "payments",
            "payment_status",
            new_column_name="status",
            existing_type=sa.String(length=32),
            existing_nullable=False,
        )
        columns = _column_names("payments")

    if "transaction_id" in columns and "transaction_reference" not in columns:
        op.alter_column(
            "payments",
            "transaction_id",
            new_column_name="transaction_reference",
            existing_type=sa.String(length=120),
            existing_nullable=False,
        )
        columns = _column_names("payments")

    if "user_id" not in columns:
        op.add_column("payments", sa.Column("user_id", sa.Integer(), nullable=True))
        columns = _column_names("payments")

    if "provider" not in columns:
        op.add_column(
            "payments",
            sa.Column("provider", sa.String(length=30), nullable=False, server_default="cash"),
        )
        columns = _column_names("payments")

    if "amount" not in columns:
        op.add_column(
            "payments",
            sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=True),
        )
        columns = _column_names("payments")

    if "updated_at" not in columns:
        op.add_column(
            "payments",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        columns = _column_names("payments")

    if "transaction_reference" not in columns:
        op.add_column(
            "payments",
            sa.Column("transaction_reference", sa.String(length=120), nullable=True),
        )
        columns = _column_names("payments")

    if "status" not in columns:
        op.add_column(
            "payments",
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        )
        columns = _column_names("payments")

    payment_mode_source = "orders.payment_mode" if "payment_mode" in order_columns else "'cash'"
    order_user_source = "orders.student_id" if "student_id" in order_columns else "payments.user_id"
    op.execute(
        sa.text(
            f"""
            UPDATE payments
            SET user_id = COALESCE(payments.user_id, {order_user_source}),
                provider = COALESCE(NULLIF(provider, ''), COALESCE({payment_mode_source}, 'cash')),
                amount = COALESCE(amount, orders.total_amount),
                updated_at = COALESCE(updated_at, payments.created_at, now())
            FROM orders
            WHERE orders.id = payments.order_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE payments
            SET status = CASE lower(COALESCE(status, 'pending'))
                WHEN 'paid' THEN 'paid'
                WHEN 'success' THEN 'paid'
                WHEN 'completed' THEN 'paid'
                WHEN 'complete' THEN 'paid'
                WHEN 'failed' THEN 'failed'
                WHEN 'failure' THEN 'failed'
                WHEN 'cancelled' THEN 'failed'
                WHEN 'canceled' THEN 'failed'
                ELSE 'pending'
            END
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE orders
            SET payment_status = CASE
                WHEN payments.status = 'paid' THEN 'paid'
                WHEN payments.status = 'failed' THEN 'failed'
                ELSE 'pending'
            END
            FROM payments
            WHERE payments.order_id = orders.id
            """
        )
    )

    payments_user_fk = _foreign_key_name("payments", ["user_id"], "users")
    if payments_user_fk is None:
        op.create_foreign_key(
            op.f("fk_payments_user_id_users"),
            "payments",
            "users",
            ["user_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    if not _index_exists("payments", op.f("ix_payments_user_id")):
        op.create_index(op.f("ix_payments_user_id"), "payments", ["user_id"], unique=False)
    if not _index_exists("payments", op.f("ix_payments_transaction_reference")):
        op.create_index(
            op.f("ix_payments_transaction_reference"),
            "payments",
            ["transaction_reference"],
            unique=False,
        )


def upgrade() -> None:
    """Upgrade the legacy Flask schema in place for the FastAPI service."""

    _ensure_roles_table()
    _migrate_users_table()
    _migrate_outlets_table()
    _migrate_menu_items_table()
    _migrate_orders_table()
    _migrate_order_items_table()
    _migrate_payments_table()


def downgrade() -> None:
    """Downgrade is intentionally unsupported for the legacy compatibility migration."""

    raise NotImplementedError("Legacy schema compatibility migration cannot be downgraded safely.")
