"""remove out-of-scope department, request, and personal Telegram features

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("expense_requests")
    op.drop_table("telegram_link_codes")
    op.execute(
        "DELETE FROM audit_logs "
        "WHERE entity_type IN ('expense_request', 'department') "
        "OR action IN ('approve', 'reject')"
    )

    # Old reminder records targeted personal accounts, not the configured shared chat.
    op.drop_table("reminder_logs")
    op.create_table(
        "reminder_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occurrence_id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.String(length=255), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["occurrence_id"], ["payment_occurrences.id"],
            name=op.f("fk_reminder_logs_occurrence_id_payment_occurrences"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reminder_logs")),
        sa.UniqueConstraint("occurrence_id", "chat_id", name="uq_reminder_once"),
    )
    op.create_index(
        op.f("ix_reminder_logs_occurrence_id"),
        "reminder_logs",
        ["occurrence_id"],
        unique=False,
    )

    with op.batch_alter_table("payment_occurrences") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_payment_occurrences_department_id_departments"),
            type_="foreignkey",
        )
        batch_op.drop_index(op.f("ix_payment_occurrences_department_id"))
        batch_op.drop_column("department_id")

    with op.batch_alter_table("recurring_payments") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_recurring_payments_department_id_departments"),
            type_="foreignkey",
        )
        batch_op.drop_index(op.f("ix_recurring_payments_department_id"))
        batch_op.drop_column("department_id")

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_audit_logs_department_id_departments"),
            type_="foreignkey",
        )
        batch_op.drop_index("ix_audit_dept_created")
        batch_op.drop_column("department_id")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint(op.f("fk_users_department_id_departments"), type_="foreignkey")
        batch_op.drop_index(op.f("ix_users_department_id"))
        batch_op.drop_constraint(op.f("uq_users_telegram_id"), type_="unique")
        batch_op.drop_column("department_id")
        batch_op.drop_column("telegram_id")

    op.drop_index(op.f("ix_departments_id"), table_name="departments")
    op.drop_table("departments")


def downgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_departments")),
        sa.UniqueConstraint("name", name=op.f("uq_departments_name")),
    )
    op.create_index(op.f("ix_departments_id"), "departments", ["id"], unique=False)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("telegram_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_users_department_id_departments"),
            "departments",
            ["department_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(op.f("uq_users_telegram_id"), ["telegram_id"])
        batch_op.create_index(op.f("ix_users_department_id"), ["department_id"], unique=False)

    with op.batch_alter_table("recurring_payments") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_recurring_payments_department_id_departments"),
            "departments",
            ["department_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_recurring_payments_department_id"), ["department_id"], unique=False
        )

    with op.batch_alter_table("payment_occurrences") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_payment_occurrences_department_id_departments"),
            "departments",
            ["department_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_payment_occurrences_department_id"), ["department_id"], unique=False
        )

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_audit_logs_department_id_departments"),
            "departments",
            ["department_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_audit_dept_created", ["department_id", "created_at"])

    op.create_table(
        "telegram_link_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_telegram_link_codes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_link_codes")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_telegram_link_codes_code_hash")),
    )
    op.create_index(
        op.f("ix_telegram_link_codes_user_id"),
        "telegram_link_codes",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "expense_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "currency",
            sa.Enum("USD", "RUB", "EUR", name="currency", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "periodicity",
            sa.Enum("monthly", "one_time", name="periodicity", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("desired_date", sa.Date(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "approved", "rejected",
                name="expensestatus", native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.String(length=500), nullable=True),
        sa.Column("recurring_payment_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_expense_requests_ck_request_amount_positive")),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"],
            name=op.f("fk_expense_requests_author_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"],
            name=op.f("fk_expense_requests_department_id_departments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recurring_payment_id"], ["recurring_payments.id"],
            name=op.f("fk_expense_requests_recurring_payment_id_recurring_payments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["users.id"],
            name=op.f("fk_expense_requests_reviewed_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expense_requests")),
    )
    for index in ("author_id", "department_id", "id", "status"):
        op.create_index(
            op.f(f"ix_expense_requests_{index}"),
            "expense_requests",
            [index],
            unique=False,
        )

    op.drop_index(op.f("ix_reminder_logs_occurrence_id"), table_name="reminder_logs")
    op.drop_table("reminder_logs")
    op.create_table(
        "reminder_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occurrence_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["occurrence_id"], ["payment_occurrences.id"],
            name=op.f("fk_reminder_logs_occurrence_id_payment_occurrences"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_reminder_logs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reminder_logs")),
        sa.UniqueConstraint("occurrence_id", "user_id", name="uq_reminder_once"),
    )
    op.create_index(
        op.f("ix_reminder_logs_occurrence_id"),
        "reminder_logs",
        ["occurrence_id"],
        unique=False,
    )
