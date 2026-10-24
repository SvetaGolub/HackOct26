"""allow shared payments and persist auth sessions

Revision ID: a1b2c3d4e5f6
Revises: 36653bbfcb4b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "36653bbfcb4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("recurring_payments") as batch_op:
        batch_op.alter_column(
            "department_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

    with op.batch_alter_table("payment_occurrences") as batch_op:
        batch_op.alter_column(
            "department_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.drop_constraint(
            "fk_payment_occurrences_recurring_payment_id_recurring_payments",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_payment_occurrences_recurring_payment_id_recurring_payments",
            "recurring_payments",
            ["recurring_payment_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name=op.f("fk_auth_sessions_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("jti", name=op.f("uq_auth_sessions_jti")),
    )
    op.create_index(
        op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")

    with op.batch_alter_table("payment_occurrences") as batch_op:
        batch_op.drop_constraint(
            "fk_payment_occurrences_recurring_payment_id_recurring_payments",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_payment_occurrences_recurring_payment_id_recurring_payments",
            "recurring_payments",
            ["recurring_payment_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.alter_column(
            "department_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    with op.batch_alter_table("recurring_payments") as batch_op:
        batch_op.alter_column(
            "department_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
